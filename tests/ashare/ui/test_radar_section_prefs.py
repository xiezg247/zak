"""雷达主区 Tab 偏好测试。"""

from vnpy_ashare.ui.quotes.radar.section_prefs import load_radar_board_mode, save_radar_board_mode


def test_radar_board_mode_default() -> None:
    assert load_radar_board_mode() == "statistical"


def test_radar_board_mode_roundtrip(monkeypatch, tmp_path) -> None:
    from vnpy.trader.ui import QtCore

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    QtCore.QSettings.setPath(QtCore.QSettings.Format.IniFormat, QtCore.QSettings.Scope.UserScope, str(tmp_path))

    save_radar_board_mode("predictive")
    assert load_radar_board_mode() == "predictive"
    save_radar_board_mode("statistical")
    assert load_radar_board_mode() == "statistical"
