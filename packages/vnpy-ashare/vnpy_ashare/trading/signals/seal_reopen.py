"""炸板 / 回封检测（limit_list_d open_times + 分 K 状态机）。"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any, Literal, Protocol

from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.screener.hard_filters import is_at_limit_board


class _MinuteBar(Protocol):
    datetime: datetime
    high_price: float
    close_price: float


SealReopenKind = Literal["unknown", "solid", "resealed", "weak", "broken"]

_KIND_LABELS: dict[SealReopenKind, str] = {
    "unknown": "",
    "solid": "首封未开",
    "resealed": "炸板回封",
    "weak": "多次打开",
    "broken": "炸板未回封",
}

_KIND_SCORES: dict[SealReopenKind, float] = {
    "unknown": 0.0,
    "solid": 1.0,
    "resealed": 0.78,
    "weak": 0.42,
    "broken": 0.12,
}


def classify_seal_reopen(*, open_times: int | None, at_limit: bool) -> SealReopenKind:
    """基于 Tushare limit_list_d.open_times（打开次数）分类。"""
    if not at_limit:
        return "unknown"
    if open_times is None:
        return "unknown"
    times = max(0, int(open_times))
    if times <= 0:
        return "solid"
    if times == 1:
        return "resealed"
    return "weak"


def seal_reopen_score(kind: SealReopenKind) -> float:
    return _KIND_SCORES.get(kind, 0.0)


def format_seal_reopen_label(kind: SealReopenKind, *, open_times: int | None = None) -> str:
    if kind == "unknown":
        return ""
    if kind == "weak" and open_times is not None and open_times > 1:
        return f"多次打开({open_times})"
    return _KIND_LABELS.get(kind, "")


def detect_seal_reopen_from_minute_bars(
    bars: list[_MinuteBar],
    *,
    limit_price: float,
    tolerance: float = 0.002,
) -> tuple[SealReopenKind, int]:
    """分 K 状态机：统计炸板次数；收盘仍封板则视为回封。"""
    if limit_price <= 0 or not bars:
        return "unknown", 0

    threshold = limit_price * (1 - tolerance)
    break_level = limit_price * 0.995
    ordered = sorted(bars, key=lambda item: item.datetime)

    sealed = False
    breaks = 0
    for bar in ordered:
        high = float(bar.high_price)
        close = float(bar.close_price)
        if high >= threshold:
            sealed = True
        if sealed and close < break_level:
            breaks += 1
            sealed = False

    last = ordered[-1]
    at_limit_now = float(last.close_price) >= threshold or float(last.high_price) >= threshold
    if not at_limit_now:
        return "broken", breaks
    if breaks <= 0:
        return "solid", 0
    if breaks == 1:
        return "resealed", 1
    return "weak", breaks


def _parse_open_times(raw: Any) -> int | None:
    if raw in (None, ""):
        return None
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return None


def seal_reopen_from_row(row: Mapping[str, Any] | QuoteRowLike) -> tuple[SealReopenKind, str, float, int | None]:
    """从行情行读取 open_times 并返回 (kind, label, score, open_times)。"""
    at_limit = is_at_limit_board(row)
    open_times = _parse_open_times(row.get("open_times"))
    preset_kind = str(row.get("seal_reopen_kind") or "").strip()
    if preset_kind in _KIND_LABELS:
        kind: SealReopenKind = preset_kind  # type: ignore[assignment]
    else:
        kind = classify_seal_reopen(open_times=open_times, at_limit=at_limit)

    label = str(row.get("seal_reopen_label") or "").strip() or format_seal_reopen_label(kind, open_times=open_times)
    score_raw = row.get("seal_reopen_score")
    if score_raw not in (None, ""):
        try:
            score = max(0.0, min(1.0, float(score_raw)))
        except (TypeError, ValueError):
            score = seal_reopen_score(kind)
    else:
        score = seal_reopen_score(kind)
    return kind, label, score, open_times


def attach_seal_reopen_fields(row: Mapping[str, Any]) -> None:
    """就地写入 seal_reopen_kind / seal_reopen_label / seal_reopen_score。"""
    kind, label, score, open_times = seal_reopen_from_row(row)
    if kind == "unknown" and not label:
        return
    row["seal_reopen_kind"] = kind
    if label:
        row["seal_reopen_label"] = label
    if score > 0:
        row["seal_reopen_score"] = score
    if open_times is not None:
        row["open_times"] = open_times
