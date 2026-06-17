"""雷达预测模型模式偏好测试。"""

from vnpy_ashare.quotes.radar.predict.predict_prefs import load_predict_model_mode, save_predict_model_mode


def test_predict_model_mode_roundtrip(monkeypatch, tmp_path) -> None:
    from vnpy.trader.ui import QtCore

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(tmp_path))

    save_predict_model_mode("baseline")
    assert load_predict_model_mode() == "baseline"
    save_predict_model_mode("auto")
    assert load_predict_model_mode() == "auto"


def test_predict_model_mode_migrates_legacy_lgb(monkeypatch, tmp_path) -> None:
    from vnpy.trader.ui import QtCore

    from vnpy_ashare.config.preferences._settings import get_settings

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(tmp_path))

    get_settings().setValue("quotes/radar/predict_model_mode", "lgb")
    assert load_predict_model_mode() == "baseline"
