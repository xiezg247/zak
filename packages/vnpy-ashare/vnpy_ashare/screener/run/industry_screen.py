"""行业成分选股执行。"""

from __future__ import annotations

from vnpy_ashare.domain.market.quote_row import QuoteRowsLike
from vnpy_ashare.domain.screener.result_row import coerce_screener_result_rows
from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.run.result import ScreenerRunResult, build_screener_run_result
from vnpy_ashare.screener.sector.sector_summary import attach_industry


def run_industry_screen(
    industry: str,
    *,
    top_n: int = 50,
    quote_rows: QuoteRowsLike | None = None,
) -> ScreenerRunResult:
    """筛选指定行业成分股，按涨幅降序取 top_n。"""
    label = (industry or "").strip()
    if not label:
        raise ValueError("行业名称不能为空")
    if quote_rows is None:
        snapshot = load_screening_quote_snapshot()
        quote_rows = snapshot.rows
    if not quote_rows:
        raise RuntimeError("暂无行情数据，请先刷新全市场行情。")

    enriched = attach_industry(quote_rows)
    matched = [row for row in enriched if str(row.get("industry") or "").strip() == label]
    if not matched:
        raise RuntimeError(f"未找到行业「{label}」的成分股，请检查行业映射是否已同步。")

    filtered = apply_recipe_filters(matched)
    sorted_rows = sorted(filtered, key=lambda row: float(row.get("change_pct") or 0), reverse=True)
    top_n = max(1, min(int(top_n or 50), 200))
    updated_at = format_china_datetime()
    return build_screener_run_result(
        rows=coerce_screener_result_rows(sorted_rows[:top_n]),
        condition=f"{label} 成分",
        updated_at=updated_at,
        total_scanned=len(matched),
        source="industry",
    )
