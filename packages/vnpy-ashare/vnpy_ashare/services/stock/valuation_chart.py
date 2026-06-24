"""估值历史序列（供 AI 迷你图）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.storage.repositories.valuation import list_valuation_history

_MAX_POINTS = 60


def _format_trade_date(trade_date: str) -> str:
    cleaned = str(trade_date or "").strip()
    if len(cleaned) == 8 and cleaned.isdigit():
        return f"{cleaned[:4]}-{cleaned[4:6]}-{cleaned[6:8]}"
    return cleaned


def _series_from_history(
    ts_code: str,
    *,
    field: str,
    limit: int = 120,
) -> list[dict[str, Any]]:
    history = list_valuation_history(ts_code, limit=max(10, min(int(limit or 120), 250)))
    ordered = sorted(history, key=lambda row: row.trade_date)
    rows: list[dict[str, Any]] = []
    for row in ordered:
        raw = getattr(row, field, None)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value <= 0:
            continue
        rows.append({"date": _format_trade_date(row.trade_date), "value": round(value, 2)})
    return rows[-_MAX_POINTS:]


def build_valuation_chart_series(ts_code: str, *, limit: int = 120) -> dict[str, list[dict[str, Any]]]:
    """返回 PE / PB 折线序列（空列表表示无本地估值历史）。"""
    return {
        "pe_ttm": _series_from_history(ts_code, field="pe_ttm", limit=limit),
        "pb": _series_from_history(ts_code, field="pb", limit=limit),
    }
