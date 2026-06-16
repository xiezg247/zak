"""雷达模型训练对话框状态文案。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.ui.quotes.radar.train_dialog import build_radar_predict_train_status


def test_build_status_when_lightgbm_missing() -> None:
    with patch(
        "vnpy_ashare.ui.quotes.radar.train_dialog.lightgbm_available",
        return_value=False,
    ):
        status = build_radar_predict_train_status()
    assert status.can_train is False
    assert "LightGBM" in status.headline


def test_build_status_when_no_artifact() -> None:
    with (
        patch(
            "vnpy_ashare.ui.quotes.radar.train_dialog.lightgbm_available",
            return_value=True,
        ),
        patch(
            "vnpy_ashare.ui.quotes.radar.train_dialog.model_artifact_exists",
            return_value=False,
        ),
    ):
        status = build_radar_predict_train_status()
    assert status.can_train is True
    assert status.retrain_recommended is True
    assert "尚无" in status.headline


def test_build_status_when_model_fresh() -> None:
    manifest = {"trained_at": "2026-06-01T12:00:00", "val_auc": 0.62, "sample_count": 12000}
    with (
        patch(
            "vnpy_ashare.ui.quotes.radar.train_dialog.lightgbm_available",
            return_value=True,
        ),
        patch(
            "vnpy_ashare.ui.quotes.radar.train_dialog.model_artifact_exists",
            return_value=True,
        ),
        patch(
            "vnpy_ashare.ui.quotes.radar.train_dialog.load_manifest",
            return_value=manifest,
        ),
        patch(
            "vnpy_ashare.ui.quotes.radar.train_dialog.manifest_model_age_days",
            return_value=5,
        ),
        patch(
            "vnpy_ashare.ui.quotes.radar.train_dialog.should_retrain_predict_model",
            return_value=False,
        ),
        patch(
            "vnpy_ashare.ui.quotes.radar.train_dialog.manifest_model_caption",
            return_value="验证 AUC 0.62",
        ),
    ):
        status = build_radar_predict_train_status()
    assert status.headline == "模型可用"
    assert "验证 AUC" in status.detail
