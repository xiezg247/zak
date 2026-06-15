"""板块资金聚合。"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any

from vnpy.trader.utility import ZoneInfo

from vnpy_ashare.ai.context.store import get_market_quotes_cache
from vnpy_ashare.domain.sector_flow import SectorFlowRow, SectorFlowSnapshot
from vnpy_ashare.integrations.tushare.factors import fetch_stock_industry_map
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, load_market_quote_rows
from vnpy_ashare.screener.sector.sector_summary import attach_industry
from vnpy_ashare.services.base import BaseService

_CHINA_TZ = ZoneInfo("Asia/Shanghai")
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
    return datetime.now(_CHINA_TZ).strftime("%Y-%m-%d")


def _proxy_flow_yi(row: dict[str, Any]) -> float:
    net_mf = float(row.get("net_mf_amount") or 0)
    if net_mf != 0:
        return net_mf / 10000.0
    amount = float(row.get("amount") or 0)
    change = float(row.get("change_pct") or 0)
    if amount <= 0:
        return 0.0
    return amount * change / 100.0 / 1e8


def _flow_source_for_rows(items: list[dict[str, Any]]) -> str:
    if any(float(row.get("net_mf_amount") or 0) != 0 for row in items):
        return "tushare"
    return "proxy"


def diagnose_sector_flow_empty(
    rows: list[dict[str, Any]],
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
    rows: list[dict[str, Any]],
    *,
    industry_map: dict[str, str] | None = None,
) -> list[SectorFlowRow]:
    """按 Tushare 行业聚合板块资金与强度。"""
    enriched = attach_industry(rows, industry_map=industry_map)
    if not enriched:
        return []

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
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
            )
        )

    inflow_rows, outflow_rows = split_sector_display_rows(result)
    return inflow_rows + outflow_rows


def build_sector_snapshot(
    rows: list[dict[str, Any]],
    *,
    updated_at: str | None,
    industry_map: dict[str, str] | None = None,
) -> SectorFlowSnapshot:
    sector_rows = aggregate_sector_rows(rows, industry_map=industry_map)
    inflow_rows = [row for row in sector_rows if row.net_flow_yi > 0]
    outflow_rows = [row for row in sector_rows if row.net_flow_yi < 0]
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
    empty_hint = ""
    if not sector_rows and rows:
        empty_hint = diagnose_sector_flow_empty(rows, raw_total=len(rows), industry_map=industry_map)
    return SectorFlowSnapshot(
        rows=tuple(sector_rows),
        inflow_rows=tuple(inflow_rows),
        outflow_rows=tuple(outflow_rows),
        updated_at=updated_at or "",
        trade_date=_today_trade_date(),
        top_inflow_name=top_in_name,
        top_inflow_yi=top_in_yi,
        top_outflow_name=top_out_name,
        top_outflow_yi=top_out_yi,
        empty_hint=empty_hint,
    )


class SectorFlowService(BaseService):
    """板块资金快照。"""

    def _resolve_quote_rows(self) -> tuple[list[dict[str, Any]], str | None, int, str | None]:
        """优先使用市场页全量缓存，否则从 Redis 拉全市场（不做逐股 Tushare enrich）。"""
        quote_svc = getattr(self.engine, "quote_service", None)
        if quote_svc is not None:
            cached = quote_svc.get_market_quotes_cache()
        else:
            cached = get_market_quotes_cache()
        if len(cached) >= _MIN_CACHE_ROWS_FOR_SECTOR:
            return cached, None, len(cached), None

        try:
            market = load_market_quote_rows(enrich_factors=False)
        except MarketQuotesLoadError as ex:
            return [], None, 0, str(ex)
        return market.rows, market.updated_at, market.total, None

    def load_snapshot(self) -> SectorFlowSnapshot:
        rows, updated_at, total, error = self._resolve_quote_rows()
        if error:
            return SectorFlowSnapshot(rows=(), empty_hint=error)
        if not rows:
            return SectorFlowSnapshot(rows=(), empty_hint="Redis 无有效行情快照。请到「工具 → 立即执行 → 行情采集」运行后再刷新。")

        industry_map = fetch_stock_industry_map()
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
            )
        return snapshot
