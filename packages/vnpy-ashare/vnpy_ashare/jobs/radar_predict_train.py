"""雷达预测模型 Walk-forward 重训定时任务。"""

from __future__ import annotations

from datetime import time

from vnpy_ashare.domain.calendar import is_trading_day
from vnpy_ashare.domain.datetime import china_now
from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.quotes.radar.predict.model_paths import (
    lightgbm_available,
    lightgbm_unavailable_hint,
    should_retrain_predict_model,
)
from vnpy_ashare.quotes.radar.predict.predict_scan import run_predict_scan
from vnpy_ashare.quotes.radar.predict.train_ranker import run_train_radar_ranker

_DEFAULT_MAX_AGE_DAYS = 30


def run_radar_predict_train_job(*, force: bool = False, max_age_days: int = _DEFAULT_MAX_AGE_DAYS) -> JobResult:
    """盘后按需重训 LightGBM，并刷新预测卡缓存。"""
    now = china_now()
    if not force:
        if not is_trading_day(now.date()):
            return JobResult(success=True, skipped=True, message="非交易日，已跳过")
        if now.time() < time(15, 0):
            return JobResult(success=True, skipped=True, message="尚未收盘，已跳过")

    if not lightgbm_available():
        return JobResult(
            success=True,
            skipped=True,
            message=f"LightGBM 未就绪，已跳过（{lightgbm_unavailable_hint()}）",
        )

    if not force and not should_retrain_predict_model(max_age_days=max_age_days):
        try:
            predict = run_predict_scan()
        except Exception as ex:
            return JobResult(success=False, message=f"预测扫描失败：{ex}")
        return JobResult(
            success=True,
            skipped=True,
            message=f"模型未过期（<{max_age_days} 天），仅刷新预测缓存 {len(predict.rows)} 只（{predict.model_label}）",
        )

    train = run_train_radar_ranker()
    if not train.success:
        return JobResult(success=False, message=train.message)

    try:
        predict = run_predict_scan()
    except Exception as ex:
        return JobResult(success=False, message=f"训练成功但预测扫描失败：{ex}")

    note = ""
    if force:
        note = "强制执行 · "
    elif not is_trading_day(now.date()):
        note = "非交易日强制执行 · "
    elif now.time() < time(15, 0):
        note = "盘前强制执行 · "

    auc = f"{train.val_auc:.3f}" if train.val_auc is not None else "—"
    return JobResult(
        success=True,
        message=(f"{note}雷达预测重训完成：验证 AUC {auc} · 样本 {train.sample_count} · 预测缓存 {len(predict.rows)} 只（{predict.model_label}）"),
    )
