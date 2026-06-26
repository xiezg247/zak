"""信号区「理由」列委托：绘制可点击文字，替代逐行 QToolButton。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

IndexType = QtCore.QModelIndex | QtCore.QPersistentModelIndex


class SignalInfoColumnDelegate(QtWidgets.QStyledItemDelegate):
    """最后一列显示「理由」，单击打开详情。"""

    reason_requested = QtCore.Signal(int)

    def paint(
        self,
        painter: QtGui.QPainter,
        option: QtWidgets.QStyleOptionViewItem,
        index: IndexType,
    ) -> None:
        opt = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = "理由"
        opt.displayAlignment = QtCore.Qt.AlignmentFlag.AlignCenter
        widget = opt.widget
        if widget is not None:
            style = widget.style()
            if style is not None:
                style.drawControl(QtWidgets.QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
                return
        super().paint(painter, opt, index)

    def editorEvent(
        self,
        event: QtCore.QEvent,
        model: QtCore.QAbstractItemModel,
        option: QtWidgets.QStyleOptionViewItem,
        index: IndexType,
    ) -> bool:
        if (
            event.type() == QtCore.QEvent.Type.MouseButtonRelease
            and isinstance(event, QtGui.QMouseEvent)
            and event.button() == QtCore.Qt.MouseButton.LeftButton
            and option.rect.contains(event.position().toPoint())
        ):
            self.reason_requested.emit(index.row())
            return True
        return super().editorEvent(event, model, option, index)
