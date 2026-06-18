"""板块资金聚合。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, QuoteRowsLike
from vnpy_ashare.domain.market.sector_flow import SectorFlowHistoryPoint, SectorFlowRow, SectorFlowSnapshot
from vnpy_ashare.domain.time.china import format_china_date
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.integrations.tushare.factors import fetch_stock_industry_map
from vnpy_ashare.integrations.tushare.sector_moneyflow import (
    fetch_moneyflow_cnt_ths_with_fallback,
    fetch_moneyflow_ind_dc_with_fallback,
    fetch_sector_flow_history_from_tushare,
)
from vnpy_ashare.quotes.core.quote_rows import get_market_quotes_cache
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, load_market_quote_rows
from vnpy_ashare.screener.sector.sector_summary import attach_industry
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.services.sector_constituents import compute_divergence_rows, load_sector_leaders, resolve_concept_vt_symbols
from vnpy_ashare.storage.repositories.sector_flow_history import (
    load_sector_flow_history,
    merge_sector_flow_history,
    upsert_sector_flow_day,
    upsert_sector_history_points,
)

_MIN_STOCKS = 3
_TOP_EACH_SIDE = 24
_MIN_CACHE_ROWS_FOR_SECTOR = 500


def split_sector_display_rows(
    rows: list[SectorFlowRow],
) -> tuple[list[SectorFlowRow], list[SectorFlowRow]]:
    """净流入 / 净流出各取 Top N（避免只按净流入截断导致净流出榜消失）。"""
    inflow = sorted(
        [row for row in rows if row.net_flow_yi > 0],
        key=lambda item: item.net_flow_yi,
        reverse=True,
    )[:_TOP_EACH_SIDE]
    outflow = sorted(
        [row for row in rows if row.net_flow_yi < 0],
        key=lambda item: item.net_flow_yi,
    )[:_TOP_EACH_SIDE]
    return inflow, outflow


def _today_trade_date() -> str:
    return format_china_date()


def _proxy_flow_yi(row: QuoteRowLike) -> float:
    net_mf = float(row.get("net_mf_amount") or 0)
    if net_mf != 0:
        return net_mf / 10000.0
    amount = float(row.get("amount") or 0)
    change = float(row.get("change_pct") or 0)
    if amount <= 0:
        return 0.0
    return amount * change / 100.0 / 1e8


def _flow_source_for_rows(items: QuoteRowsLike) -> str:
    if any(float(row.get("net_mf_amount") or 0) != 0 for row in items):
        return "tushare"
    return "proxy"


def diagnose_sector_flow_empty(
    rows: QuoteRowsLike,
    *,
    raw_total: int,
    industry_map: dict[str, str] | None = None,
) -> str:
    """根据行情与行业映射情况生成空状态引导文案。"""
    if raw_total <= 0:
        return "Redis 无有效行情快照。请到「工具 → 立即执行 → 行情采集」运行后再刷新。"
    enriched = attach_industry(rows, industry_map=industry_map)
    if not enriched:
        return "全市场行情已加载，但无法匹配行业字段。请配置 TUSHARE_TOKEN，并运行「工具 → 定时任务 → 同步行业映射」后再刷新。"
    buckets: dict[str, int] = defaultdict(int)
    for row in enriched:
        industry = str(row.get("industry") or "").strip()
        if industry:
            buckets[industry] += 1
    qualifying = sum(1 for count in buckets.values() if count >= _MIN_STOCKS)
    if qualifying == 0:
        return (
            f"当前仅展示成分不少于 {_MIN_STOCKS} 只的行业；已映射 {len(enriched)} 只股票、{len(buckets)} 个行业标签，但均无足够成分。请检查行业映射是否过稀疏。"
        )
    return "暂无板块数据，请稍后刷新。"


def aggregate_sector_rows(
    rows: QuoteRowsLike,
    *,
    industry_map: dict[str, str] | None = None,
) -> list[SectorFlowRow]:
    """按 Tushare 行业聚合板块资金与强度。"""
    enriched = attach_industry(rows, industry_map=industry_map)
    if not enriched:
        return []

    buckets: dict[str, list[QuoteRow]] = defaultdict(list)
    for row in enriched:
        industry = str(row.get("industry") or "").strip()
        if industry:
            buckets[industry].append(row)

    result: list[SectorFlowRow] = []
    for industry, items in buckets.items():
        if len(items) < _MIN_STOCKS:
            continue
        changes = [float(item.get("change_pct") or 0) for item in items]
        avg_change = sum(changes) / len(changes)
        up_count = sum(1 for value in changes if value > 0)
        up_ratio = up_count / len(items)
        strength = round(up_ratio * 100 + avg_change, 2)
        net_yi = sum(_proxy_flow_yi(item) for item in items)
        source = _flow_source_for_rows(items)

        result.append(
            SectorFlowRow(
                sector_id=industry,
                name=industry,
                strength=strength,
                change_pct=round(avg_change, 2),
                net_flow_yi=round(net_yi, 2),
                stock_count=len(items),
                up_ratio=round(up_ratio, 4),
                flow_source=source,
                sector_kind="industry",
            )
        )

    inflow_rows, outflow_rows = split_sector_display_rows(result)
    return inflow_rows + outflow_rows


def _format_trade_date_label(trade_date: str) -> str:
    cleaned = str(trade_date or "").strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
    return cleaned


def rows_from_dc_moneyflow(
    rows: QuoteRowsLike,
    *,
    sector_kind: str,
    flow_source: str,
    top_each_side: int | None = _TOP_EACH_SIDE,
) -> list[SectorFlowRow]:
    """东财板块 API 行 → SectorFlowRow。"""
    result: list[SectorFlowRow] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        change_pct = float(row.get("pct_change") or 0)
        net_rate = float(row.get("net_amount_rate") or 0)
        net_yi = float(row.get("net_amount") or 0) / 1e8
        sector_id = str(row.get("ts_code") or name).strip()
        result.append(
            SectorFlowRow(
                sector_id=sector_id,
                name=name,
                strength=round(change_pct + net_rate, 2),
                change_pct=round(change_pct, 2),
                net_flow_yi=round(net_yi, 2),
                stock_count=0,
                up_ratio=0.0,
                flow_source=flow_source,
                sector_kind=sector_kind,
                leader_stock=str(row.get("leader_stock") or "").strip(),
                net_flow_rate=round(net_rate, 2),
            )
        )
    if top_each_side is None:
        return result
    inflow_rows, outflow_rows = split_sector_display_rows(result)
    return inflow_rows + outflow_rows


def rows_from_ths_concept_moneyflow(
    rows: QuoteRowsLike,
    *,
    top_each_side: int | None = _TOP_EACH_SIDE,
) -> list[SectorFlowRow]:
    """同花顺概念板块 API 行 → SectorFlowRow。"""
    result: list[SectorFlowRow] = []
    for row in rows:
        name = str(row.get("name") or "").strip()
        if not name:
            continue
        change_pct = float(row.get("pct_change") or 0)
        net_yi = float(row.get("net_amount") or 0)
        leader_change = float(row.get("leader_change_pct") or 0)
        sector_id = str(row.get("ts_code") or name).strip()
        result.append(
            SectorFlowRow(
                sector_id=sector_id,
                name=name,
                strength=round(change_pct + leader_change * 0.2, 2),
                change_pct=round(change_pct, 2),
                net_flow_yi=round(net_yi, 2),
                stock_count=int(row.get("company_num") or 0),
                up_ratio=0.0,
                flow_source="ths_concept",
                sector_kind="concept",
                leader_stock=str(row.get("leader_stock") or "").strip(),
                net_flow_rate=0.0,
            )
        )
    if top_each_side is None:
        return result
    inflow_rows, outflow_rows = split_sector_display_rows(result)
    return inflow_rows + outflow_rows


def _snapshot_from_rows(
    sector_rows: list[SectorFlowRow],
    *,
    updated_at: str,
    trade_date: str,
    sector_kind: str,
    data_mode: str,
    empty_hint: str = "",
) -> SectorFlowSnapshot:
    inflow_rows = [row for row in sector_rows if row.net_flow_yi > 0]
    outflow_rows = [row for row in sector_rows if row.net_flow_yi < 0]
    divergence_rows = tuple(compute_divergence_rows(sector_rows))
    top_in_name = top_out_name = ""
    top_in_yi = 0.0
    top_out_yi = 0.0
    if inflow_rows:
        top_in = inflow_rows[0]
        top_in_name = top_in.name
        top_in_yi = top_in.net_flow_yi
    if outflow_rows:
        top_out = outflow_rows[0]
        top_out_name = top_out.name
        top_out_yi = top_out.net_flow_yi
    return SectorFlowSnapshot(
        rows=tuple(sector_rows),
        inflow_rows=tuple(inflow_rows),
        outflow_rows=tuple(outflow_rows),
        divergence_rows=divergence_rows,
        updated_at=updated_at,
        trade_date=trade_date,
        top_inflow_name=top_in_name,
        top_inflow_yi=top_in_yi,
        top_outflow_name=top_out_name,
        top_outflow_yi=top_out_yi,
        empty_hint=empty_hint,
        sector_kind=sector_kind,
        data_mode=data_mode,
    )


def _persist_official_history(snapshot: SectorFlowSnapshot) -> None:
    if snapshot.data_mode not in {"official_dc", "official_ths"}:
        return
    if not snapshot.rows or not snapshot.trade_date:
        return
    upsert_sector_flow_day(snapshot.trade_date, snapshot.sector_kind, list(snapshot.rows))


def build_official_snapshot(
    sector_rows: list[SectorFlowRow],
    *,
    trade_date: str,
    sector_kind: str,
    data_mode: str,
) -> SectorFlowSnapshot:
    label = _format_trade_date_label(trade_date)
    return _snapshot_from_rows(
        sector_rows,
        updated_at=f"日终 {label}" if label else "",
        trade_date=trade_date,
        sector_kind=sector_kind,
        data_mode=data_mode,
    )


def finalize_official_snapshot(snapshot: SectorFlowSnapshot) -> SectorFlowSnapshot:
    _persist_official_history(snapshot)
    return snapshot


def build_sector_snapshot(
    rows: QuoteRowsLike,
    *,
    updated_at: str | None,
    industry_map: dict[str, str] | None = None,
) -> SectorFlowSnapshot:
    sector_rows = aggregate_sector_rows(rows, industry_map=industry_map)
    empty_hint = ""
    if not sector_rows and rows:
        empty_hint = diagnose_sector_flow_empty(rows, raw_total=len(rows), industry_map=industry_map)
    return _snapshot_from_rows(
        sector_rows,
        updated_at=updated_at or "",
        trade_date=_today_trade_date(),
        sector_kind="industry",
        data_mode="intraday",
        empty_hint=empty_hint,
    )


class SectorFlowService(BaseService):
    """板块资金快照。"""

    def __init__(self, engine: Any) -> None:
        super().__init__(engine)
        self._last_quote_rows: QuoteRowsLike = []
        self._last_industry_map: dict[str, str] | None = None

    def _cache_quote_context(self, rows: QuoteRowsLike, industry_map: dict[str, str] | None = None) -> None:
        self._last_quote_rows = list(rows)
        if industry_map is not None:
            self._last_industry_map = industry_map

    def load_sector_leaders(self, sector: SectorFlowRow, *, limit: int = 5) -> list:
        if not self._last_quote_rows:
            rows, _, _, _ = self._resolve_quote_rows()
            self._cache_quote_context(rows, fetch_stock_industry_map() if rows else None)
        return load_sector_leaders(
            sector,
            self._last_quote_rows,
            industry_map=self._last_industry_map,
            limit=limit,
        )

    def load_sector_history(self, sector: SectorFlowRow, *, limit: int = 5) -> list[SectorFlowHistoryPoint]:
        local = load_sector_flow_history(
            sector_id=sector.sector_id,
            sector_kind=sector.sector_kind,
            limit=limit,
        )
        if len(local) >= limit:
            return local
        remote = fetch_sector_flow_history_from_tushare(sector, limit=limit)
        if not remote:
            return local
        local_dates = {point.trade_date for point in local}
        backfill = [point for point in remote if point.trade_date not in local_dates]
        if backfill:
            upsert_sector_history_points(sector, backfill)
        return merge_sector_flow_history(local, remote, limit=limit)

    def resolve_concept_vt_symbols(self, sector: SectorFlowRow) -> list[str]:

        return sorted(resolve_concept_vt_symbols(sector))

    def _resolve_quote_rows(self) -> tuple[list[QuoteRow], str | None, int, str | None]:
        """优先使用市场页全量缓存，否则从 Redis 拉全市场（不做逐股 Tushare enrich）。"""
        quote_svc = getattr(self.engine, "quote_service", None)
        if quote_svc is not None:
            cached = quote_svc.get_market_quotes_cache()
        else:
            cached = get_market_quotes_cache()
        if len(cached) >= _MIN_CACHE_ROWS_FOR_SECTOR:
            return list(cached), None, len(cached), None

        try:
            market = load_market_quote_rows(enrich_factors=False)
        except MarketQuotesLoadError as ex:
            return [], None, 0, str(ex)
        return list(market.rows), market.updated_at, market.total, None

    def load_snapshot(self, *, sector_kind: str = "industry") -> SectorFlowSnapshot:
        kind = str(sector_kind or "industry").strip().lower()
        if kind == "concept":
            return self._load_concept_snapshot()
        return self._load_industry_snapshot()

    def _load_concept_snapshot(self) -> SectorFlowSnapshot:
        rows, _, _, _ = self._resolve_quote_rows()
        self._cache_quote_context(rows)
        ths_rows, trade_date = fetch_moneyflow_cnt_ths_with_fallback()
        if ths_rows:
            sector_rows = rows_from_ths_concept_moneyflow(ths_rows)
            if sector_rows:
                return finalize_official_snapshot(
                    build_official_snapshot(
                        sector_rows,
                        trade_date=trade_date,
                        sector_kind="concept",
                        data_mode="official_ths",
                    )
                )
        dc_rows, trade_date = fetch_moneyflow_ind_dc_with_fallback(content_type="概念")
        if dc_rows:
            sector_rows = rows_from_dc_moneyflow(dc_rows, sector_kind="concept", flow_source="dc_concept")
            if sector_rows:
                return finalize_official_snapshot(
                    build_official_snapshot(
                        sector_rows,
                        trade_date=trade_date,
                        sector_kind="concept",
                        data_mode="official_dc",
                    )
                )
        return SectorFlowSnapshot(
            rows=(),
            empty_hint="暂无概念板块资金数据。请配置 TUSHARE_TOKEN（需板块资金流积分），盘后刷新。",
            sector_kind="concept",
            data_mode="official_ths",
        )

    def _load_industry_snapshot(self) -> SectorFlowSnapshot:
        rows, _, _, _ = self._resolve_quote_rows()
        industry_map = fetch_stock_industry_map()
        self._cache_quote_context(rows, industry_map)
        if not is_ashare_trading_session():
            dc_rows, trade_date = fetch_moneyflow_ind_dc_with_fallback(content_type="行业")
            if dc_rows:
                sector_rows = rows_from_dc_moneyflow(dc_rows, sector_kind="industry", flow_source="dc_industry")
                if sector_rows:
                    return finalize_official_snapshot(
                        build_official_snapshot(
                            sector_rows,
                            trade_date=trade_date,
                            sector_kind="industry",
                            data_mode="official_dc",
                        )
                    )
        return self._load_intraday_industry_snapshot()

    def _load_intraday_industry_snapshot(self) -> SectorFlowSnapshot:
        rows, updated_at, total, error = self._resolve_quote_rows()
        if error:
            return SectorFlowSnapshot(rows=(), empty_hint=error)
        if not rows:
            return SectorFlowSnapshot(rows=(), empty_hint="Redis 无有效行情快照。请到「工具 → 立即执行 → 行情采集」运行后再刷新。")

        industry_map = fetch_stock_industry_map()
        self._cache_quote_context(rows, industry_map)
        snapshot = build_sector_snapshot(
            rows,
            updated_at=updated_at,
            industry_map=industry_map,
        )
        if not snapshot.rows and not snapshot.empty_hint:
            hint = diagnose_sector_flow_empty(rows, raw_total=total, industry_map=industry_map)
            snapshot = SectorFlowSnapshot(
                rows=snapshot.rows,
                inflow_rows=snapshot.inflow_rows,
                outflow_rows=snapshot.outflow_rows,
                updated_at=snapshot.updated_at,
                trade_date=snapshot.trade_date,
                top_inflow_name=snapshot.top_inflow_name,
                top_inflow_yi=snapshot.top_inflow_yi,
                top_outflow_name=snapshot.top_outflow_name,
                top_outflow_yi=snapshot.top_outflow_yi,
                empty_hint=hint,
                sector_kind="industry",
                data_mode="intraday",
            )
        if snapshot.rows and is_ashare_trading_session():
            snapshot = SectorFlowSnapshot(
                rows=snapshot.rows,
                inflow_rows=snapshot.inflow_rows,
                outflow_rows=snapshot.outflow_rows,
                updated_at=(snapshot.updated_at or "") + " · 盘中估算",
                trade_date=snapshot.trade_date,
                top_inflow_name=snapshot.top_inflow_name,
                top_inflow_yi=snapshot.top_inflow_yi,
                top_outflow_name=snapshot.top_outflow_name,
                top_outflow_yi=snapshot.top_outflow_yi,
                empty_hint=snapshot.empty_hint,
                sector_kind="industry",
                data_mode="intraday",
            )
        return snapshot
