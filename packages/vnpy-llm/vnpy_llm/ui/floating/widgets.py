"""悬浮球 / 全屏助手快捷动作 UI。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_common.ai.protocol import QuickAction

_FLOATING_MAX_PRIMARY = 5


def _flatten_action_for_overflow_menu(action: QuickAction) -> list[QuickAction]:
    """将带子菜单的项展开为扁平列表，供「更多」一级菜单展示。"""
    if not action.has_menu:
        return [action]
    return [child.model_copy(update={"label": f"{action.label}·{child.label}"}) for child in action.children]


def compact_quick_actions_for_display(
    actions: list[QuickAction],
    *,
    layout_mode: str = "assistant",
    max_primary: int = _FLOATING_MAX_PRIMARY,
) -> list[QuickAction]:
    """悬浮/紧凑面板：超过上限时收进「更多」二级菜单。"""
    if layout_mode == "assistant" or len(actions) <= max_primary:
        return actions
    budget = max(1, max_primary - 1)
    primary = actions[:budget]
    overflow_flat: list[QuickAction] = []
    for action in actions[budget:]:
        overflow_flat.extend(_flatten_action_for_overflow_menu(action))
    if not overflow_flat:
        return primary
    more = QuickAction(
        id="more_actions",
        label="更多",
        tooltip="更多快捷指令",
        children=overflow_flat,
    )
    return [*primary, more]


class QuickActionChips(QtWidgets.QWidget):
    """横向快捷动作按钮条，支持二级菜单。"""

    triggered = QtCore.Signal(object)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("AiQuickActionChips")
        self._layout = QtWidgets.QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._scroll = QtWidgets.QScrollArea()
        self._scroll.setObjectName("AiQuickActionScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._scroll.setMaximumHeight(42)

        self._inner = QtWidgets.QWidget()
        self._inner.setObjectName("AiQuickActionInner")
        self._inner_layout = QtWidgets.QHBoxLayout(self._inner)
        self._inner_layout.setContentsMargins(0, 0, 0, 0)
        self._inner_layout.setSpacing(6)
        self._inner_layout.addStretch()
        self._scroll.setWidget(self._inner)

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self._layout.addWidget(self._scroll)

    def set_actions(self, actions: list[QuickAction], *, layout_mode: str = "assistant") -> None:
        display = compact_quick_actions_for_display(actions, layout_mode=layout_mode)
        while self._inner_layout.count() > 1:
            item = self._inner_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for action in display:
            widget = self._build_action_widget(action)
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, widget)
        self.setVisible(bool(actions))

    def _build_action_widget(self, action: QuickAction) -> QtWidgets.QWidget:
        if action.has_menu:
            tool_btn = QtWidgets.QToolButton()
            tool_btn.setObjectName("AiQuickActionBtn")
            tool_btn.setText(action.label)
            tool_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            tool_btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
            tool_btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            tool_btn.setArrowType(QtCore.Qt.ArrowType.NoArrow)
            menu = QtWidgets.QMenu(tool_btn)
            menu.setObjectName("AiQuickActionMenu")
            for child in action.children:

                def _emit_child(*, _item: QuickAction = child) -> None:
                    self.triggered.emit(_item)

                menu.addAction(child.label, _emit_child)
            tool_btn.setMenu(menu)
            if action.tooltip:
                tool_btn.setToolTip(action.tooltip)
            return tool_btn

        plain_btn = QtWidgets.QPushButton(action.label)
        plain_btn.setObjectName("AiQuickActionBtn")
        plain_btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        if action.tooltip:
            plain_btn.setToolTip(action.tooltip)
        plain_btn.clicked.connect(lambda checked=False, item=action: self.triggered.emit(item))
        return plain_btn
