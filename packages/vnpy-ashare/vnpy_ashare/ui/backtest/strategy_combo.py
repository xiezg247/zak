"""策略回测页：下拉展示中文名，内部仍用 class_name。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from strategies.registry import get_strategy_meta


def strategy_display_title(class_name: str) -> str:
    meta = get_strategy_meta(class_name)
    return meta.title if meta else class_name


class StrategyClassCombo(QtWidgets.QComboBox):
    """展示策略中文名；currentText() 与 vnpy 回测引擎兼容，返回 class_name。"""

    def current_class_name(self) -> str:
        data = self.currentData(QtCore.Qt.ItemDataRole.UserRole)
        if data is not None:
            return str(data)
        return super().currentText().strip()

    def current_display_title(self) -> str:
        return super().currentText().strip()

    def currentText(self) -> str:
        return self.current_class_name()

    def findText(self, text: str, flags: QtCore.Qt.MatchFlag = QtCore.Qt.MatchFlag.MatchExactly) -> int:
        target = text.strip()
        if not target:
            return -1
        for index in range(self.count()):
            if self.itemData(index, QtCore.Qt.ItemDataRole.UserRole) == target:
                return index
        return super().findText(text, flags)

    def set_strategy_items(self, class_names: list[str]) -> None:
        self.clear()
        for class_name in class_names:
            self.addItem(strategy_display_title(class_name), class_name)
