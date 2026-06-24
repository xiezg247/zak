"""dialog_shell 尺寸逻辑测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtCore

from vnpy_common.ui.dialog_shell import setup_responsive_dialog


def test_setup_responsive_dialog_matches_size_reference() -> None:
    dialog = MagicMock()
    host = MagicMock()
    host.isWindow.return_value = False
    host.width.return_value = 1400
    host.height.return_value = 900
    host.mapToGlobal.return_value = QtCore.QPoint(120, 80)
    host.size.return_value = QtCore.QSize(1400, 900)

    with patch(
        "vnpy_common.ui.dialog_shell.fit_dialog_to_reference_rect",
    ) as fit_mock:
        setup_responsive_dialog(
            dialog,
            None,
            min_width=1320,
            min_height=920,
            size_reference=host,
        )

    fit_mock.assert_called_once()
    rect = fit_mock.call_args[0][1]
    assert rect.x() == 120
    assert rect.y() == 80
    assert rect.width() == 1400
    assert rect.height() == 900
    assert fit_mock.call_args.kwargs == {"min_width": 1320, "min_height": 920}


def test_setup_responsive_dialog_caps_minimum_to_reference() -> None:
    from vnpy_common.ui.panel_widgets import fit_dialog_to_reference_rect

    dialog = MagicMock()
    frame = MagicMock()
    frame.width.return_value = 1024
    frame.height.return_value = 768
    frame.left.return_value = 0
    frame.top.return_value = 0
    dialog.frameGeometry.return_value = frame
    rect = QtCore.QRect(0, 0, 1024, 768)

    fit_dialog_to_reference_rect(dialog, rect, min_width=1320, min_height=920)

    dialog.setMinimumSize.assert_called_once_with(1024, 768)
    dialog.setMaximumSize.assert_called_once_with(1024, 768)
    dialog.resize.assert_called_with(1024, 768)
