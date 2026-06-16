"""雷达未来展望全市场扫描定时任务。"""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

from vnpy_ashare.domain.calendar import is_trading_day
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.quotes.radar.radar_horizon_scan import run_horizon_outlook_scan

_SHANGHAI_TZ = ZoneInfo("Asia/Shanghai")


def run_horizon_outlook_scan_job(*, force: bool = False) -> JobResult:
    """盘后全市场展望扫描：关注 / 可持 / 情景 / 预测基线。"""
    now = datetime.now(_SHANGHAI_TZ)
    if not force:
        if not is_trading_day(now.date()):
            return JobResult(
                success=True,
                skipped=True,
                message="非交易日，已跳过",
            )
        if now.time() < time(15, 0):
            return JobResult(
                success=True,
                skipped=True,
                message="尚未收盘，已跳过",
            )

    try:
        results = run_horizon_outlook_scan()
        from vnpy_ashare.quotes.radar.predict.predict_scan import run_predict_scan

        predict = run_predict_scan()
    except Exception as ex:
        return JobResult(success=False, message=f"雷达展望扫描失败：{ex}")

    if not results:
        return JobResult(success=False, message="雷达展望扫描未产出结果")

    by_variant = {item.variant: item for item in results}
    watch = by_variant.get("watch_next")
    hold = by_variant.get("hold_next")
    bull = by_variant.get("scenario_bull")
    volatile = by_variant.get("scenario_volatile")
    bear = by_variant.get("scenario_bear")
    scanned = watch.stats.scanned_total if watch else 0
    excluded = watch.stats.excluded_count if watch else 0
    prefilter = watch.stats.prefilter_total if watch else 0
    refined = watch.stats.refined_total if watch else 0
    note = ""
    if not force and not is_trading_day(now.date()):
        note = "非交易日强制执行 · "
    elif not force and now.time() < time(15, 0):
        note = "盘前强制执行 · "

    return JobResult(
        success=True,
        message=(
            f"{note}雷达展望扫描完成：全市场 {scanned} 只，排除 {excluded}，粗筛 {prefilter} / 可算 {refined} · "
            f"关注 {len(watch.rows) if watch else 0} / 可持 {len(hold.rows) if hold else 0} · "
            f"情景 多{len(bull.rows) if bull else 0}/波{len(volatile.rows) if volatile else 0}/空{len(bear.rows) if bear else 0} · "
            f"预测 {len(predict.rows)}（{predict.model_label}）"
        ),
    )
