"""信号区「理由」列委托：仅处理点击，绘制走 Model 预计算单元格。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

IndexType = QtCore.QModelIndex | QtCore.QPersistentModelIndex


class SignalInfoColumnDelegate(QtWidgets.QStyledItemDelegate):
    """最后一列「理由」；文本与样式由 Worker 写入 QuoteCell，主线程仅处理点击。"""

    reason_requested = QtCore.Signal(int)

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
