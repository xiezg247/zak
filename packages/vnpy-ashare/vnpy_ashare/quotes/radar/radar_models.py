"""雷达页共享数据模型与行情合并工具。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.domain.symbols import parse_stock_symbol, parse_tickflow_symbol
from vnpy_ashare.quotes.core.quote_rows import quote_rows_by_vt_symbol
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.quotes.radar.radar_relative_strength import enrich_radar_row_relative_strength
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError


class RadarRow(FrozenModel):
    vt_symbol: str = Field(description="合约代码（含交易所）")
    name: str = Field(description="证券名称")
    symbol: str = Field(description="证券代码")
    price: float | None = Field(description="最新价")
    change_pct: float | None = Field(description="涨跌幅（%）")
    metric_label: str = Field(description="主指标标签")
    metric_value: str = Field(description="主指标值")
    sub_label: str = Field(description="副指标标签")
    sub_value: str = Field(description="副指标值")
    leader_score: float | None = Field(default=None, description="龙头评分")
    leader_tier: str = Field(default="", description="龙头分层（龙一/龙二/跟风）")
    limit_times: float | None = Field(default=None, description="连板数")


class RadarCardData(FrozenModel):
    card_id: str = Field(description="卡片唯一标识")
    title: str = Field(description="卡片标题")
    subtitle: str = Field(description="卡片副标题")
    rows: tuple[RadarRow, ...] = Field(description="卡片行数据")
    empty_message: str = Field(description="无数据时的提示文案")
    updated_at: str = Field(description="数据更新时间")
    run_id: str = Field(default="", description="选股任务运行 ID")
    detail_page_key: str = Field(default="", description="详情页跳转键")
    total_count: int = Field(default=0, description="符合条件的标的总数")
    ai_hint: str = Field(default="", description="AI 分析提示语")
    sector_names: tuple[str, ...] = Field(default=(), description="关联板块名称")


class RadarResonanceEntry(FrozenModel):
    vt_symbol: str = Field(description="合约代码（含交易所）")
    name: str = Field(description="证券名称")
    symbol: str = Field(description="证券代码")
    card_count: int = Field(description="共振卡片数量")
    card_titles: tuple[str, ...] = Field(description="共振卡片标题列表")
    price: float | None = Field(description="最新价")
    change_pct: float | None = Field(description="涨跌幅（%）")
    resonance_score: float = Field(default=0.0, description="共振得分")


def quote_map() -> dict[str, dict[str, Any]]:
    """vt_symbol → 行情行（读进程内缓存）。"""
    return quote_rows_by_vt_symbol()


def merge_row_quotes(row: dict[str, Any]) -> dict[str, Any]:
    """合并行情缓存，补全 volume / amount / 现价等字段。"""
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    merged = dict(row)
    quote = quote_map().get(vt_symbol, {})
    for key in (
        "volume",
        "amount",
        "change_pct",
        "last_price",
        "close",
        "turnover_rate",
        "volume_ratio",
        "net_mf_amount",
        "name",
    ):
        cached = quote.get(key)
        if cached in (None, "", 0, 0.0):
            continue
        if not merged.get(key):
            merged[key] = cached
    return merged


def _ingest_quote_row(
    row: dict[str, Any],
    *,
    by_vt: dict[str, dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    symbol = str(row.get("symbol") or "").strip()
    if not vt_symbol and symbol:
        item = parse_stock_symbol(symbol)
        if item is not None:
            vt_symbol = item.vt_symbol
            row = dict(row)
            row["vt_symbol"] = vt_symbol
    if vt_symbol:
        by_vt[vt_symbol] = dict(row)
    if symbol:
        by_symbol[symbol] = dict(row)


def quotes_for_vt_symbols(vt_symbols: list[str]) -> dict[str, dict[str, Any]]:
    """批量补全行情：内存缓存 → 全市场筛选快照 → Redis 逐只。"""
    by_vt: dict[str, dict[str, Any]] = {}
    by_symbol: dict[str, dict[str, Any]] = {}

    for row in quote_map().values():
        _ingest_quote_row(row, by_vt=by_vt, by_symbol=by_symbol)

    try:
        snapshot = load_screening_quote_snapshot()
        for row in snapshot.rows:
            _ingest_quote_row(dict(row), by_vt=by_vt, by_symbol=by_symbol)
    except MarketQuotesLoadError:
        pass

    missing_tf: list[str] = []
    for vt_symbol in vt_symbols:
        if vt_symbol in by_vt:
            continue
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            continue
        if item.symbol in by_symbol:
            merged = dict(by_symbol[item.symbol])
            merged["vt_symbol"] = vt_symbol
            by_vt[vt_symbol] = merged
            continue
        missing_tf.append(item.tickflow_symbol)

    if missing_tf:
        try:

            quotes = RedisQuoteStore().get_quotes(missing_tf)
            for tf_symbol, quote in quotes.items():
                item = parse_tickflow_symbol(tf_symbol, quote.name)
                if item is None:
                    continue
                _ingest_quote_row(
                    {
                        "vt_symbol": item.vt_symbol,
                        "symbol": item.symbol,
                        "name": quote.name or item.name,
                        "last_price": quote.last_price,
                        "close": quote.last_price,
                        "change_pct": quote.change_pct,
                        "turnover_rate": quote.turnover_rate,
                        "volume": quote.volume,
                        "amount": quote.amount,
                    },
                    by_vt=by_vt,
                    by_symbol=by_symbol,
                )
        except Exception:
            pass

    result: dict[str, dict[str, Any]] = {}
    for vt_symbol in vt_symbols:
        if vt_symbol in by_vt:
            result[vt_symbol] = by_vt[vt_symbol]
        else:
            item = parse_stock_symbol(vt_symbol)
            result[vt_symbol] = {
                "vt_symbol": vt_symbol,
                "symbol": item.symbol if item else vt_symbol.split(".")[0],
            }
    return result


def enrich_radar_row(row: RadarRow, quote: dict[str, Any]) -> RadarRow:
    """用全市场行情补全 RadarRow 的现价、涨幅与相对强度副标题。"""

    merged = merge_row_quotes(quote)
    price = float_or_none(merged.get("last_price") or merged.get("close"))
    if price is None:
        price = row.price
    change_pct = float_or_none(
        merged.get("change_pct") or quote.get("change_pct") or quote.get("pct_chg"),
    )
    if change_pct is None:
        change_pct = row.change_pct
    updated = row
    if price != row.price or change_pct != row.change_pct:
        updated = row.model_copy(update={"price": price, "change_pct": change_pct})
    return enrich_radar_row_relative_strength(updated, merged)


def enrich_radar_rows(rows: tuple[RadarRow, ...]) -> tuple[RadarRow, ...]:
    """批量补全雷达行行情字段。"""
    if not rows:
        return rows
    quotes = quotes_for_vt_symbols([row.vt_symbol for row in rows])
    return tuple(enrich_radar_row(row, quotes.get(row.vt_symbol, {"vt_symbol": row.vt_symbol})) for row in rows)


def radar_row_to_cache_dict(row: RadarRow) -> dict[str, Any]:
    """RadarRow → SQLite 缓存 JSON 条目。"""
    payload: dict[str, Any] = {
        "vt_symbol": row.vt_symbol,
        "name": row.name,
        "symbol": row.symbol,
        "metric_label": row.metric_label,
        "metric_value": row.metric_value,
        "sub_label": row.sub_label,
        "sub_value": row.sub_value,
    }
    if row.price is not None:
        payload["last_close"] = row.price
    if row.change_pct is not None:
        payload["change_pct"] = row.change_pct
    return payload


def radar_row_from_cache_dict(raw: dict[str, Any], *, quote: dict[str, Any] | None = None) -> RadarRow:
    """SQLite 缓存 JSON 条目 → RadarRow（可选合并实时行情）。"""
    vt_symbol = str(raw.get("vt_symbol") or "").strip()
    base = quote if quote is not None else {"vt_symbol": vt_symbol}
    row = RadarRow(
        vt_symbol=vt_symbol,
        name=str(raw.get("name") or ""),
        symbol=str(raw.get("symbol") or ""),
        price=float_or_none(raw.get("last_close")),
        change_pct=float_or_none(raw.get("change_pct")),
        metric_label=str(raw.get("metric_label") or ""),
        metric_value=str(raw.get("metric_value") or ""),
        sub_label=str(raw.get("sub_label") or ""),
        sub_value=str(raw.get("sub_value") or ""),
    )
    return enrich_radar_row(row, base)
