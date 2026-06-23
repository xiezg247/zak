"""本地数据弹窗测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.ui.shell.local.dialog import LocalDataDialog, show_local_data_dialog


def test_local_data_dialog_has_close_button() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    _ = app

    dialog = LocalDataDialog(MagicMock(), MagicMock())
    footer = dialog.findChild(QtWidgets.QWidget, "LocalDataDialogFooter")
    assert footer is not None
    close_button = footer.findChild(QtWidgets.QPushButton)
    assert close_button is not None
    assert close_button.text() == "关闭"


def test_show_local_data_dialog_exec() -> None:
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    _ = app

    with patch("vnpy_ashare.ui.shell.local.dialog.LocalDataDialog") as mock_dialog_cls:
        mock_dialog = MagicMock()
        mock_dialog_cls.return_value = mock_dialog
        show_local_data_dialog(MagicMock(), MagicMock(), parent=MagicMock())
    mock_dialog.exec.assert_called_once()
