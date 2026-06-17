"""板块资金日终同步（行业/概念官方榜 → sector_flow_daily）。"""

from __future__ import annotations

import os

from vnpy_ashare.integrations.tushare import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.sector_moneyflow import (
    fetch_moneyflow_cnt_ths,
    fetch_moneyflow_ind_dc,
)
from vnpy_ashare.jobs.core.progress import job_log
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.screener.data.data_source import iter_trade_date_strs
from vnpy_ashare.services.sector_flow import rows_from_dc_moneyflow, rows_from_ths_concept_moneyflow
from vnpy_ashare.storage.repositories.sector_flow_history import upsert_sector_flow_day


def _sync_lookback_days() -> int:
    raw = os.getenv("SECTOR_FLOW_SYNC_DAYS", "5").strip()
    try:
        return max(1, min(int(raw), 10))
    except ValueError:
        return 5


def sync_sector_flow_daily_job() -> JobResult:
    """收盘后拉取近 N 日东财行业 + 同花顺概念板块资金，写入 sector_flow_daily。"""
    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    lookback = _sync_lookback_days()
    job_log(f"同步近 {lookback} 日板块资金（东财行业 + 同花顺概念）…")
    summaries: list[str] = []

    for trade_date in iter_trade_date_strs(max_lookback=lookback):
        day_parts: list[str] = []

        dc_industry, _ = fetch_moneyflow_ind_dc(trade_date=trade_date, content_type="行业")
        if dc_industry:
            industry_rows = rows_from_dc_moneyflow(
                dc_industry,
                sector_kind="industry",
                flow_source="dc_industry",
                top_each_side=None,
            )
            upsert_sector_flow_day(trade_date, "industry", industry_rows)
            day_parts.append(f"行业{len(industry_rows)}")

        ths_rows, _ = fetch_moneyflow_cnt_ths(trade_date=trade_date)
        if ths_rows:
            concept_rows = rows_from_ths_concept_moneyflow(ths_rows, top_each_side=None)
            upsert_sector_flow_day(trade_date, "concept", concept_rows)
            day_parts.append(f"概念{len(concept_rows)}")
        else:
            dc_concept, _ = fetch_moneyflow_ind_dc(trade_date=trade_date, content_type="概念")
            if dc_concept:
                concept_rows = rows_from_dc_moneyflow(
                    dc_concept,
                    sector_kind="concept",
                    flow_source="dc_concept",
                    top_each_side=None,
                )
                upsert_sector_flow_day(trade_date, "concept", concept_rows)
                day_parts.append(f"概念东财{len(concept_rows)}")

        if day_parts:
            summaries.append(f"{trade_date}:{'/'.join(day_parts)}")

    if not summaries:
        return JobResult(
            success=False,
            message="未同步到板块资金数据（可能非交易日、Tushare 尚未更新或权限不足）",
        )
    return JobResult(success=True, message="板块资金同步 " + "，".join(summaries))
