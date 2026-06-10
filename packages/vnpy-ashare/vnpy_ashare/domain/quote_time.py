"""行情时间字段解析与展示。"""

from __future__ import annotations


def normalize_datetime_text(value: str) -> str:
    return value.strip().replace("T", " ")


def is_missing_time_value(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.lower() in {"nat", "nan", "none"}


def format_trade_time_display(trade_time: str) -> str:
    """单条行情更新时间 → 仅时间部分（HH:MM:SS）。"""
    text = normalize_datetime_text(trade_time)
    if not text:
        return "—"
    if " " in text:
        return text.split(" ", 1)[1]
    return text


def format_batch_updated_at(value: str | None) -> str:
    """Redis 批次 meta 时间 → MM-DD HH:MM:SS。"""
    text = normalize_datetime_text(value or "")
    if not text:
        return ""
    if " " not in text:
        return text
    date_part, time_part = text.split(" ", 1)
    if len(date_part) >= 10:
        return f"{date_part[5:]} {time_part}"
    return text


def resolve_trade_time_from_tickflow_row(row: dict) -> str:
    raw = row.get("trade_time")
    if not is_missing_time_value(raw):
        return normalize_datetime_text(str(raw))

    symbol = str(row.get("symbol", "") or "")
    timestamp = row.get("timestamp")
    if symbol and timestamp is not None:
        try:
            from tickflow.utils import instrument_timestamp_to_trade_time

            return instrument_timestamp_to_trade_time(symbol, int(float(timestamp)), unit="ms")
        except Exception:
            return ""
    return ""
