"""持仓·风控 loader（隔日退出规则）。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.domain.trading.exit import RuleStatus
from vnpy_ashare.domain.trading.position import PositionRecord
from vnpy_ashare.quotes.core.provider import quote_snapshot_from_row
from vnpy_ashare.quotes.format import format_pct
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, merge_row_quotes
from vnpy_ashare.storage.repositories.positions import load_position_rows
from vnpy_ashare.storage.repositories.symbols import build_symbol_name_map
from vnpy_ashare.trading.exit.overnight_exit import evaluate_overnight_exit

_STATUS_RANK: dict[RuleStatus, int] = {
    "triggered": 0,
    "near": 1,
    "clear": 2,
}


def _row_float(value: str | float | int | None) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return 0.0


def _row_int(value: str | float | int | None) -> int:
    return int(_row_float(value))


def _worst_rule_status(rules) -> RuleStatus:
    if not rules:
        return "clear"
    best = "clear"
    for rule in rules:
        status = str(rule.status)
        if status in _STATUS_RANK and _STATUS_RANK[status] < _STATUS_RANK.get(best, 99):
            best = status  # type: ignore[assignment]
    return best  # type: ignore[return-value]


def _evaluation_rank(evaluation) -> tuple[int, int]:
    signal_rank = 0 if evaluation.signal == "sell" else 1
    status = _worst_rule_status(evaluation.rules)
    return signal_rank, _STATUS_RANK.get(status, 9)


def load_position_risk(spec: RadarCardSpec) -> RadarCardData:
    rows_db = load_position_rows()
    if not rows_db:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="暂无持仓记账",
            rows=(),
            empty_message="持仓区为空，请在自选页登记头寸。",
            updated_at=format_china_datetime_minute(),
        )

    name_map = build_symbol_name_map()
    evaluated: list[tuple[PositionRecord, object, tuple[int, int]]] = []
    for row in rows_db:
        exchange = Exchange(str(row["exchange"]))
        symbol = str(row["symbol"])
        record = PositionRecord(
            symbol=symbol,
            exchange=exchange.value,
            name=name_map.get((symbol, exchange), ""),
            cost_price=_row_float(row["cost_price"]),
            volume=_row_int(row["volume"]),
            buy_date=str(row["buy_date"]),
            notes=str(row.get("notes") or ""),
            source=str(row.get("source") or "manual"),  # type: ignore[arg-type]
            plan_pct=row.get("plan_pct"),  # type: ignore[arg-type]
        )
        quote_row = merge_row_quotes({"vt_symbol": record.vt_symbol})
        quote = quote_snapshot_from_row(quote_row, tickflow_symbol=symbol)
        evaluation = evaluate_overnight_exit(record, quote=quote)
        evaluated.append((record, evaluation, _evaluation_rank(evaluation)))

    evaluated.sort(key=lambda item: item[2])
    radar_rows: list[RadarRow] = []
    triggered = near = 0
    for record, evaluation, _rank in evaluated[: spec.top_n]:
        quote_row = merge_row_quotes({"vt_symbol": record.vt_symbol})
        change_raw = quote_row.get("change_pct")
        change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
        price_raw = quote_row.get("last_price") or quote_row.get("close")
        price = float(price_raw) if isinstance(price_raw, (int, float)) else None

        status = _worst_rule_status(evaluation.rules)
        if status == "triggered":
            triggered += 1
        elif status == "near":
            near += 1

        top_rule = evaluation.rules[0] if evaluation.rules else None
        metric_label = top_rule.label if top_rule is not None else evaluation.signal
        metric_value = top_rule.detail[:12] if top_rule is not None and top_rule.detail else evaluation.signal
        pnl_pct = None
        if price is not None and record.cost_price > 0:
            pnl_pct = round((price - record.cost_price) / record.cost_price * 100, 2)

        radar_rows.append(
            RadarRow(
                vt_symbol=record.vt_symbol,
                name=record.name or record.symbol,
                symbol=record.symbol,
                price=price,
                change_pct=change_pct,
                metric_label=str(metric_label),
                metric_value=str(metric_value)[:12],
                sub_label="浮盈" if pnl_pct is not None else "信号",
                sub_value=format_pct(pnl_pct) if pnl_pct is not None else evaluation.signal,
            )
        )

    subtitle_parts = [f"持仓 {len(rows_db)} 只"]
    if triggered:
        subtitle_parts.append(f"触发 {triggered}")
    if near:
        subtitle_parts.append(f"临近 {near}")
    subtitle = " · ".join(subtitle_parts)

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=tuple(radar_rows),
        empty_message="",
        updated_at=format_china_datetime_minute(),
        total_count=len(radar_rows),
    )
