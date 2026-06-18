"""单票 / 全持仓隔日退出评估（AI Skill 入口）。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.domain.trading.position import PositionRecord, position_t1_locked
from vnpy_ashare.quotes.core.provider import quote_snapshot_from_row
from vnpy_ashare.quotes.radar.radar_models import quotes_for_vt_symbols
from vnpy_ashare.storage.repositories.positions import load_position_row, load_position_rows
from vnpy_ashare.storage.repositories.symbols import build_symbol_name_map
from vnpy_ashare.trading.exit.overnight_exit import evaluate_overnight_exit

__all__ = ["evaluate_all_overnight_exits", "evaluate_overnight_exit_for_symbol"]

_DISCLAIMER = "规则参考，不构成买卖建议；T+1 锁定日不可卖。"


def _row_float(value: object) -> float:
    if isinstance(value, bool):
        raise TypeError("invalid numeric field")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError("missing numeric field")


def _row_int(value: object) -> int:
    return int(_row_float(value))


def _record_from_db_row(row: dict[str, object], *, name: str) -> PositionRecord:
    return PositionRecord(
        symbol=str(row["symbol"]),
        exchange=str(row["exchange"]),
        name=name,
        cost_price=_row_float(row["cost_price"]),
        volume=_row_int(row["volume"]),
        buy_date=str(row["buy_date"]),
        notes=str(row.get("notes") or ""),
        source=str(row.get("source") or "manual"),  # type: ignore[arg-type]
        plan_pct=row.get("plan_pct"),  # type: ignore[arg-type]
    )


def _quote_summary(record: PositionRecord, quote_row: dict[str, Any] | None) -> dict[str, object] | None:
    item = parse_stock_symbol(record.vt_symbol)
    tickflow = item.tickflow_symbol if item is not None else record.symbol
    quote = quote_snapshot_from_row(quote_row or {}, tickflow_symbol=tickflow)
    if quote is None or quote.last_price <= 0:
        return None
    pnl_pct = None
    if record.cost_price > 0:
        pnl_pct = round((quote.last_price - record.cost_price) / record.cost_price * 100, 2)
    return {
        "last_price": quote.last_price,
        "change_pct": quote.change_pct,
        "open_price": quote.open_price,
        "prev_close": quote.prev_close,
        "volume_ratio": quote.volume_ratio,
        "unrealized_pnl_pct": pnl_pct,
    }


def _evaluate_record(record: PositionRecord, *, quote_row: dict[str, Any] | None) -> dict[str, Any]:
    item = parse_stock_symbol(record.vt_symbol)
    tickflow = item.tickflow_symbol if item is not None else record.symbol
    quote = quote_snapshot_from_row(quote_row or {}, tickflow_symbol=tickflow)
    evaluation = evaluate_overnight_exit(record, quote=quote)
    payload = evaluation.to_dict()
    payload.update(
        {
            "vt_symbol": record.vt_symbol,
            "name": record.name,
            "cost_price": record.cost_price,
            "volume": record.volume,
            "buy_date": record.buy_date,
            "t1_locked": position_t1_locked(record.buy_date),
            "quote": _quote_summary(record, quote_row),
        },
    )
    return payload


def evaluate_overnight_exit_for_symbol(symbol: str) -> dict[str, Any]:
    """评估单票隔日退出规则（须已登记持仓）。"""
    item = parse_stock_symbol(symbol)
    if item is None:
        return {"error": f"无法解析代码: {symbol}"}

    row = load_position_row(item.symbol, item.exchange)
    if row is None:
        return {
            "error": f"未登记持仓：{item.vt_symbol}，请先在自选页持仓区登记后再检查隔日卖点",
        }

    name_map = build_symbol_name_map()
    name = name_map.get((item.symbol, item.exchange), item.name)
    record = _record_from_db_row(row, name=name)
    quotes = quotes_for_vt_symbols([item.vt_symbol])
    payload = _evaluate_record(record, quote_row=quotes.get(item.vt_symbol))
    payload["disclaimer"] = _DISCLAIMER
    return payload


def evaluate_all_overnight_exits() -> dict[str, Any]:
    """扫描全部登记持仓的隔日退出规则。"""
    rows = load_position_rows()
    if not rows:
        return {"items": [], "sell_count": 0, "hold_count": 0, "disclaimer": _DISCLAIMER}

    name_map = build_symbol_name_map()
    vt_symbols: list[str] = []
    records: list[PositionRecord] = []
    for row in rows:
        exchange = Exchange(str(row["exchange"]))
        symbol = str(row["symbol"])
        vt_symbol = f"{symbol}.{exchange.name}"
        vt_symbols.append(vt_symbol)
        name = name_map.get((symbol, exchange), "")
        records.append(_record_from_db_row(row, name=name))

    quotes = quotes_for_vt_symbols(vt_symbols)
    items = [_evaluate_record(record, quote_row=quotes.get(record.vt_symbol)) for record in records]
    sell_count = sum(1 for item in items if item.get("signal") == "sell")
    hold_count = sum(1 for item in items if item.get("signal") == "hold")
    return {
        "items": items,
        "sell_count": sell_count,
        "hold_count": hold_count,
        "disclaimer": _DISCLAIMER,
    }
