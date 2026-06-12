"""标准弹窗布局：响应式尺寸、居中、Header/Content/Footer 壳。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_common.ui.panel_widgets import center_dialog_on_parent, initial_dialog_size


def setup_responsive_dialog(
    dialog: QtWidgets.QDialog,
    parent: QtWidgets.QWidget | None,
    *,
    min_width: int = 1080,
    min_height: int = 760,
) -> None:
    """按屏幕比例设置弹窗最小/初始尺寸并居中。"""
    dialog.setMinimumSize(min_width, min_height)
    width, height = initial_dialog_size(min_width=min_width, min_height=min_height)
    dialog.resize(width, height)
    center_dialog_on_parent(dialog, parent)


def apply_standard_dialog_layout(
    dialog: QtWidgets.QDialog,
    *,
    header: QtWidgets.QWidget | None = None,
    content: QtWidgets.QWidget,
    footer: QtWidgets.QWidget | None = None,
    margins: tuple[int, int, int, int] = (16, 14, 16, 12),
    spacing: int = 12,
    content_stretch: int = 1,
) -> QtWidgets.QVBoxLayout:
    layout = QtWidgets.QVBoxLayout(dialog)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    if header is not None:
        layout.addWidget(header)
    layout.addWidget(content, stretch=content_stretch)
    if footer is not None:
        layout.addWidget(footer)
    return layout


def build_panel_footer(
    status: QtWidgets.QLabel,
    *buttons: QtWidgets.QPushButton,
    object_name: str = "PanelFooter",
    min_button_width: int = 88,
) -> QtWidgets.QWidget:
    footer = QtWidgets.QWidget()
    footer.setObjectName(object_name)
    row = QtWidgets.QHBoxLayout(footer)
    row.setContentsMargins(0, 8, 0, 0)
    row.addWidget(status, stretch=1)
    for button in buttons:
        button.setMinimumWidth(min_button_width)
        row.addWidget(button)
    return footer


def set_panel_status_loading(label: QtWidgets.QLabel, loading: bool) -> None:
    label.setProperty("loading", loading)
    style = label.style()
    style.unpolish(label)
    style.polish(label)
