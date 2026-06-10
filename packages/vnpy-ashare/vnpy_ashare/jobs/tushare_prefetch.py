"""Tushare 因子预拉取（写入 app_db 日级缓存）。"""

from __future__ import annotations

from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.screener.data_source import fetch_daily_basic_with_fallback, fetch_moneyflow_with_fallback
from vnpy_ashare.screener.factors import fetch_daily_pct_map, fetch_stock_industry_map
from vnpy_ashare.screener.tushare_client import TushareNotConfiguredError, get_tushare_pro


def prefetch_tushare_factors() -> JobResult:
    """拉取 daily_basic / moneyflow / daily_pct / stock_industry 到本地缓存。

    供定时任务或「立即执行」调用；选股路径命中缓存后不再打 API。
    """
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    parts: list[str] = []
    basic_rows, basic_date = fetch_daily_basic_with_fallback()
    parts.append(f"daily_basic {len(basic_rows)} 条 @ {basic_date or '-'}")

    mf_rows, mf_date = fetch_moneyflow_with_fallback()
    parts.append(f"moneyflow {len(mf_rows)} 条 @ {mf_date or '-'}")

    pct_date = basic_date or mf_date
    if pct_date:
        pct_map = fetch_daily_pct_map(pct_date)
        parts.append(f"daily_pct {len(pct_map)} 条 @ {pct_date}")

    industry_map = fetch_stock_industry_map()
    parts.append(f"stock_industry {len(industry_map)} 条")

    if not basic_rows and not mf_rows:
        return JobResult(
            success=False,
            message="未拉取到因子数据（可能非交易日、Tushare 尚未更新或权限不足）",
        )
    return JobResult(success=True, message="；".join(parts))
