"""QSS：vnpy 继承页（回测、数据管理等）。"""

from vnpy.trader.ui import QtWidgets

from vnpy_common.ui.theme.manager import theme_manager
from vnpy_common.ui.theme.build_extra import build_vnpy_page_stylesheet
from vnpy_common.ui.theme.tokens import DARK_TOKENS

VNPY_PAGE_STYLESHEET = build_vnpy_page_stylesheet(DARK_TOKENS)

_PRIMARY_ACTION_LABELS = frozenset({"开始回测"})


def apply_vnpy_page_style(widget, *, page_id: str) -> None:
    """vnpy 继承页：表单 / 表格 / 日志随主题切换。"""

    widget.setObjectName(page_id)
    theme_manager().bind_stylesheet(widget, extra=build_vnpy_page_stylesheet)


def style_vnpy_form_inputs(widget, *, input_name: str = "BacktestInput") -> None:
    for line in widget.findChildren(QtWidgets.QLineEdit):
        if line.objectName() in ("SearchBox", "PageJumpInput", "BacktestInput"):
            continue
        line.setObjectName(input_name)
    for date_edit in widget.findChildren(QtWidgets.QDateEdit):
        date_edit.setObjectName(input_name)


def style_vnpy_push_buttons(
    widget,
    *,
    primary_labels: frozenset[str] = _PRIMARY_ACTION_LABELS,
    skip: frozenset[str] = frozenset({"SecondaryButton", "ActionButton", "PrimaryRunButton", "DangerButton"}),
) -> None:
    for btn in widget.findChildren(QtWidgets.QPushButton):
        name = btn.objectName()
        if name in skip:
            continue
        if btn.text().strip() in primary_labels:
            btn.setObjectName("ActionButton")
        else:
            btn.setObjectName("SecondaryButton")


def apply_toolbar_combo_style(combo) -> None:
    """工具栏下拉：背景 + 高对比选项（macOS 需自定义 QListView）。"""
    combo.setObjectName("ToolbarCombo")
    view = QtWidgets.QListView(combo)
    view.setObjectName("ToolbarComboList")
    combo.setView(view)
    combo.setMinimumContentsLength(5)


def apply_settings_combo_style(combo) -> None:
    """配置页下拉：macOS 选项列表。"""
    combo.setObjectName("SettingsInput")
    view = QtWidgets.QListView(combo)
    view.setObjectName("SettingsComboList")
    combo.setView(view)
    combo.setMinimumContentsLength(8)
