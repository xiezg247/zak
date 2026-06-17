"""行情时间字段解析与展示。"""

from __future__ import annotations

from tickflow.utils import instrument_timestamp_to_trade_time

from vnpy_ashare.domain.datetime import format_china_date


def normalize_datetime_text(value: str) -> str:
    return value.strip().replace("T", " ")


def is_missing_time_value(value: object) -> bool:
    if value is None:
        return True
    text = str(value).strip()
    return not text or text.lower() in {"nat", "nan", "none"}


def format_trade_time_display(trade_time: str) -> str:
    """单条行情更新时间 → YYYY-MM-DD HH:MM:SS。"""
    text = normalize_datetime_text(trade_time)
    if not text:
        return "—"
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


def format_relative_updated_at(
    raw: str | None,
    *,
    today: str | None = None,
    prefix: str = "更新",
) -> str:
    """ISO / 空格分隔时间 → 相对展示（今日仅 HH:MM，否则 MM-DD HH:MM）。"""
    if not raw:
        return ""
    text = raw.strip()
    if "T" not in text:
        return f"{prefix} {text}" if prefix else text
    date_part, time_part = text.split("T", 1)
    time_short = time_part[:5] if len(time_part) >= 5 else time_part
    if today is None:

        today = format_china_date()
    if date_part == today:
        body = time_short
    else:
        mm_dd = date_part[5:10] if len(date_part) >= 10 else date_part
        body = f"{mm_dd} {time_short}"
    return f"{prefix} {body}" if prefix else body


def resolve_trade_time_from_tickflow_row(row: dict) -> str:
    raw = row.get("trade_time")
    if not is_missing_time_value(raw):
        return normalize_datetime_text(str(raw))

    symbol = str(row.get("symbol", "") or "")
    timestamp = row.get("timestamp")
    if symbol and timestamp is not None:
        try:

            return str(instrument_timestamp_to_trade_time(symbol, int(float(timestamp)), unit="ms"))
        except Exception:
            return ""
    return ""
