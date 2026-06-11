"""雷达页卡片数据加载（纯函数，Worker 线程调用）。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from vnpy_ashare.ai.context.store import get_market_quotes_cache
from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.radar_catalog import (
    DEFAULT_SCREEN_TASK_VARIANT,
    RADAR_CARD_SPECS,
    RadarCardSpec,
)
from vnpy_ashare.screener.dimensions.volume_surge import run_volume_surge
from vnpy_ashare.screener.run.run_store import get_latest_run, is_auto_run, is_strategy_run, list_runs


@dataclass(frozen=True)
class RadarRow:
    vt_symbol: str
    name: str
    symbol: str
    price: float | None
    change_pct: float | None
    metric_label: str
    metric_value: str
    sub_label: str
    sub_value: str


@dataclass(frozen=True)
class RadarCardData:
    card_id: str
    title: str
    subtitle: str
    rows: tuple[RadarRow, ...]
    empty_message: str
    updated_at: str


def _quote_map() -> dict[str, dict[str, Any]]:
    cached = get_market_quotes_cache()
    if not cached:
        return {}
    return {str(row.get("vt_symbol") or ""): row for row in cached if row.get("vt_symbol")}


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _format_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}%"


def _screener_metric(row: dict[str, Any]) -> tuple[str, str, str, str]:
    if "composite_score" in row:
        score = _float_or_none(row.get("composite_score"))
        return "综合分", f"{score:.1f}" if score is not None else "—", "涨幅", _format_pct(_float_or_none(row.get("change_pct")))
    change = _float_or_none(row.get("change_pct") or row.get("pct_chg"))
    turnover = _float_or_none(row.get("turnover_rate"))
    return "涨幅", _format_pct(change), "换手", f"{turnover:.2f}%" if turnover is not None else "—"


def _row_from_dict(row: dict[str, Any]) -> RadarRow | None:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return None
    item = parse_stock_symbol(vt_symbol)
    name = str(row.get("name") or (item.name if item else "") or vt_symbol)
    symbol = str(row.get("symbol") or (item.symbol if item else vt_symbol.split(".")[0]))
    quotes = _quote_map()
    quote = quotes.get(vt_symbol, row)
    price = _float_or_none(quote.get("last_price") or quote.get("close"))
    change_pct = _float_or_none(quote.get("change_pct") or row.get("change_pct") or row.get("pct_chg"))
    metric_label, metric_value, sub_label, sub_value = _screener_metric(row)
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=symbol,
        price=price,
        change_pct=change_pct,
        metric_label=metric_label,
        metric_value=metric_value,
        sub_label=sub_label,
        sub_value=sub_value,
    )


def _rows_from_screener(rows: list[dict[str, Any]], *, top_n: int) -> tuple[RadarRow, ...]:
    result: list[RadarRow] = []
    for row in rows[:top_n]:
        parsed = _row_from_dict(row)
        if parsed is not None:
            result.append(parsed)
    return tuple(result)


def _card_from_run(
    spec: RadarCardSpec,
    record,
    *,
    empty_message: str,
) -> RadarCardData:
    if record is None or not record.rows:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="",
            rows=(),
            empty_message=empty_message,
            updated_at="",
        )
    subtitle = str(record.config.get("reason_summary") or record.condition or record.created_at)
    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=_rows_from_screener(record.rows, top_n=spec.top_n),
        empty_message="",
        updated_at=record.created_at,
    )


def _find_run_for_task_variant(variant: str):
    if variant == "strategy":
        for record in list_runs(limit=30):
            if is_strategy_run(record.config):
                return record
        return None
    trigger = f"scheduled_{variant.removeprefix('scheduled_')}"
    for record in list_runs(limit=30):
        if not is_auto_run(record.config):
            continue
        if str(record.config.get("trigger", "")) == trigger:
            return record
    return None


def load_screen_latest(spec: RadarCardSpec) -> RadarCardData:
    return _card_from_run(
        spec,
        get_latest_run(),
        empty_message="暂无选股记录，请前往「策略选股」或「自动选股」运行。",
    )


def load_screen_task(spec: RadarCardSpec, *, variant: str = DEFAULT_SCREEN_TASK_VARIANT) -> RadarCardData:
    record = _find_run_for_task_variant(variant)
    label = {
        "scheduled_intraday": "盘中定时任务",
        "scheduled_post_close": "盘后定时任务",
        "strategy": "策略选股",
    }.get(variant, variant)
    empty = f"暂无「{label}」运行记录。"
    return _card_from_run(spec, record, empty_message=empty)


def load_discovery_volume_surge(spec: RadarCardSpec) -> RadarCardData:
    hits, total = run_volume_surge(spec.top_n, weight=1.0)
    if not hits:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=f"扫描 {total} 只" if total else "",
            rows=(),
            empty_message="暂无行情数据，请先采集行情或打开「市场」页。",
            updated_at="",
        )
    rows: list[RadarRow] = []
    for hit in hits:
        row = hit.row
        volume = _float_or_none(row.get("volume"))
        change = _float_or_none(row.get("change_pct"))
        parsed = _row_from_dict(row)
        if parsed is None:
            continue
        rows.append(
            RadarRow(
                vt_symbol=parsed.vt_symbol,
                name=parsed.name,
                symbol=parsed.symbol,
                price=parsed.price,
                change_pct=change if change is not None else parsed.change_pct,
                metric_label="成交量",
                metric_value=f"{volume:,.0f}" if volume is not None else "—",
                sub_label="涨幅",
                sub_value=_format_pct(change),
            )
        )
    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=f"全市场 Top {len(rows)}",
        rows=tuple(rows),
        empty_message="",
        updated_at="",
    )


def load_radar_board(
    *,
    screen_task_variant: str = DEFAULT_SCREEN_TASK_VARIANT,
) -> dict[str, RadarCardData]:
    """加载全部雷达卡片。"""
    result: dict[str, RadarCardData] = {}
    for spec in RADAR_CARD_SPECS:
        if spec.id == "screen_latest":
            result[spec.id] = load_screen_latest(spec)
        elif spec.id == "screen_task":
            result[spec.id] = load_screen_task(spec, variant=screen_task_variant)
        elif spec.id == "discovery_volume_surge":
            result[spec.id] = load_discovery_volume_surge(spec)
    return result
