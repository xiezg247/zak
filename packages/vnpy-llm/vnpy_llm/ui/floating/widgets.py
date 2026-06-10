"""悬浮球 / 全屏助手快捷动作 UI。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_common.ai.protocol import QuickAction


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

    def set_actions(self, actions: list[QuickAction]) -> None:
        while self._inner_layout.count() > 1:
            item = self._inner_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for action in actions:
            widget = self._build_action_widget(action)
            self._inner_layout.insertWidget(self._inner_layout.count() - 1, widget)
        self.setVisible(bool(actions))

    def _build_action_widget(self, action: QuickAction) -> QtWidgets.QWidget:
        if action.has_menu:
            btn = QtWidgets.QToolButton()
            btn.setObjectName("AiQuickActionBtn")
            btn.setText(action.label)
            btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            btn.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextOnly)
            btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
            btn.setArrowType(QtCore.Qt.ArrowType.NoArrow)
            menu = QtWidgets.QMenu(btn)
            menu.setObjectName("AiQuickActionMenu")
            for child in action.children:
                menu.addAction(
                    child.label,
                    lambda checked=False, item=child: self.triggered.emit(item),
                )
            btn.setMenu(menu)
            if action.tooltip:
                btn.setToolTip(action.tooltip)
            return btn

        btn = QtWidgets.QPushButton(action.label)
        btn.setObjectName("AiQuickActionBtn")
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        if action.tooltip:
            btn.setToolTip(action.tooltip)
        btn.clicked.connect(lambda checked=False, item=action: self.triggered.emit(item))
        return btn
