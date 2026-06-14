"""行业成分选股执行。"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from vnpy_ashare.screener.hard_filters import apply_screening_filters
from vnpy_ashare.screener.run.export import resolve_export_columns
from vnpy_ashare.screener.run.runner import ScreenerRunResult
from vnpy_ashare.screener.sector.sector_summary import attach_industry

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def _quote_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": row.get("symbol", ""),
        "name": row.get("name", ""),
        "vt_symbol": row.get("vt_symbol", ""),
        "last_price": row.get("last_price", 0),
        "change_pct": row.get("change_pct", 0),
        "turnover_rate": row.get("turnover_rate", 0),
        "volume": row.get("volume", 0),
        "amount": row.get("amount", 0),
        "industry": row.get("industry", ""),
        "source": row.get("source", "quote"),
    }


def run_industry_screen(
    industry: str,
    *,
    top_n: int = 50,
    quote_rows: list[dict[str, Any]] | None = None,
) -> ScreenerRunResult:
    """筛选指定行业成分股，按涨幅降序取 top_n。"""
    label = (industry or "").strip()
    if not label:
        raise ValueError("行业名称不能为空")
    if quote_rows is None:
        from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot

        snapshot = load_screening_quote_snapshot()
        quote_rows = snapshot.rows
    if not quote_rows:
        raise RuntimeError("暂无行情数据，请先刷新全市场行情。")

    enriched = attach_industry(quote_rows)
    matched = [row for row in enriched if str(row.get("industry") or "").strip() == label]
    if not matched:
        raise RuntimeError(f"未找到行业「{label}」的成分股，请检查行业映射是否已同步。")

    filtered = apply_screening_filters(matched)
    sorted_rows = sorted(filtered, key=lambda row: float(row.get("change_pct") or 0), reverse=True)
    top_n = max(1, min(int(top_n or 50), 200))
    rows = [_quote_row(row) for row in sorted_rows[:top_n]]
    updated_at = datetime.now(_SHANGHAI_TZ).strftime("%Y-%m-%d %H:%M:%S")
    return ScreenerRunResult(
        rows=rows,
        condition=f"{label} 成分",
        updated_at=updated_at,
        total_scanned=len(matched),
        source="industry",
        columns=resolve_export_columns(rows),
    )
