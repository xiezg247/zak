"""雷达预测重训任务测试。"""

from __future__ import annotations

from vnpy_ashare.jobs.radar_predict_train import run_radar_predict_train_job


def test_train_job_skips_when_model_fresh(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.jobs.radar_predict_train.is_trading_day",
        lambda _date: True,
    )
    monkeypatch.setattr(
        "vnpy_ashare.jobs.radar_predict_train.lightgbm_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "vnpy_ashare.jobs.radar_predict_train.should_retrain_predict_model",
        lambda **kwargs: False,
    )

    class _Predict:
        rows = (1, 2)
        model_label = "LightGBM"

    monkeypatch.setattr(
        "vnpy_ashare.jobs.radar_predict_train.run_predict_scan",
        lambda **kwargs: _Predict(),
    )

    result = run_radar_predict_train_job(force=False)
    assert result.skipped is True
    assert "未过期" in result.message


def test_train_job_runs_when_forced(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.jobs.radar_predict_train.lightgbm_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "vnpy_ashare.jobs.radar_predict_train.run_train_radar_ranker",
        lambda **kwargs: type(
            "Train",
            (),
            {"success": True, "message": "ok", "sample_count": 500, "val_auc": 0.61},
        )(),
    )

    class _Predict:
        rows = (1,)
        model_label = "LightGBM"

    monkeypatch.setattr(
        "vnpy_ashare.jobs.radar_predict_train.run_predict_scan",
        lambda **kwargs: _Predict(),
    )

    result = run_radar_predict_train_job(force=True)
    assert result.success is True
    assert "重训完成" in result.message
