"""交易计划 Tab：历史计划列表 + 详情。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.domain.trading.plan import TradingPlanRecord
from vnpy_ashare.storage.repositories.trading_plans import list_trading_plans
from vnpy_common.ui.panel_widgets import hint_label

_PLAN_ID_ROLE = QtCore.Qt.ItemDataRole.UserRole

_STATUS_LABELS = {
    "draft": "草案",
    "active": "已激活",
    "archived": "已归档",
}

_EMOTION_LABELS = {
    "ice": "冰点",
    "startup": "启动",
    "climax": "发酵/高潮",
    "divergence": "分歧",
    "recession": "退潮",
}


class NotesCenterPlansView(QtWidgets.QWidget):
    """全局交易计划历史（不绑定左侧标的列表）。"""

    open_plan_in_watchlist_requested = QtCore.Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("NotesCenterPlansView")

        self._list = QtWidgets.QListWidget(self)
        self._list.setObjectName("NotesCenterPlansList")
        self._list.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self._list.currentItemChanged.connect(self._on_plan_selected)

        self._detail = QtWidgets.QTextBrowser(self)
        self._detail.setObjectName("NotesCenterPlanDetail")
        self._detail.setOpenExternalLinks(False)

        self._refresh_button = QtWidgets.QPushButton("刷新", self)
        self._refresh_button.setObjectName("SecondaryButton")
        self._refresh_button.clicked.connect(self.reload)

        self._open_watchlist_button = QtWidgets.QPushButton("在自选查看", self)
        self._open_watchlist_button.setObjectName("SecondaryButton")
        self._open_watchlist_button.setEnabled(False)
        self._open_watchlist_button.clicked.connect(self._open_selected_symbol)

        self._empty_label = hint_label("暂无交易计划")
        self._empty_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        list_panel = QtWidgets.QWidget(self)
        list_layout = QtWidgets.QVBoxLayout(list_panel)
        list_layout.setContentsMargins(0, 0, 0, 0)
        list_layout.setSpacing(6)
        list_layout.addWidget(self._list, stretch=1)
        list_layout.addWidget(self._empty_label)

        detail_panel = QtWidgets.QWidget(self)
        detail_layout = QtWidgets.QVBoxLayout(detail_panel)
        detail_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout.setSpacing(6)
        detail_layout.addWidget(self._detail, stretch=1)
        button_row = QtWidgets.QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self._open_watchlist_button)
        button_row.addWidget(self._refresh_button)
        detail_layout.addLayout(button_row)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal, self)
        splitter.addWidget(list_panel)
        splitter.addWidget(detail_panel)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 540])

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(splitter)

        self._plans: list[TradingPlanRecord] = []
        self._selected_vt_symbol = ""

    def reload(self) -> None:
        self._plans = list_trading_plans(limit=50)
        self._list.blockSignals(True)
        self._list.clear()
        for plan in self._plans:
            item = QtWidgets.QListWidgetItem(_format_plan_item(plan))
            item.setData(_PLAN_ID_ROLE, plan.id)
            item.setToolTip(plan.notes or plan.trade_date)
            self._list.addItem(item)
        self._list.blockSignals(False)
        has_items = self._list.count() > 0
        self._list.setVisible(has_items)
        self._empty_label.setVisible(not has_items)
        self._open_watchlist_button.setEnabled(False)
        if has_items:
            self._list.setCurrentRow(0)
        else:
            self._detail.clear()

    def clear(self) -> None:
        self._plans = []
        self._list.clear()
        self._detail.clear()
        self._list.setVisible(False)
        self._empty_label.setVisible(True)

    def _on_plan_selected(
        self,
        current: QtWidgets.QListWidgetItem | None,
        _previous: QtWidgets.QListWidgetItem | None,
    ) -> None:
        if current is None:
            self._detail.clear()
            self._open_watchlist_button.setEnabled(False)
            self._selected_vt_symbol = ""
            return
        plan_id = str(current.data(_PLAN_ID_ROLE) or "")
        plan = next((item for item in self._plans if item.id == plan_id), None)
        if plan is None:
            self._detail.clear()
            self._open_watchlist_button.setEnabled(False)
            return
        self._detail.setPlainText(_format_plan_detail(plan))
        self._selected_vt_symbol = plan.watchlist_vt_symbols[0] if plan.watchlist_vt_symbols else ""
        self._open_watchlist_button.setEnabled(bool(self._selected_vt_symbol))

    def _open_selected_symbol(self) -> None:
        if self._selected_vt_symbol:
            self.open_plan_in_watchlist_requested.emit(self._selected_vt_symbol)


def _format_plan_item(plan: TradingPlanRecord) -> str:
    status = _STATUS_LABELS.get(plan.status, plan.status)
    symbol_count = len(plan.symbols)
    pct = int(round(plan.max_position_pct * 100))
    return f"{plan.trade_date} · {status}\n仓位 ≤{pct}% · {symbol_count} 只"


def _format_plan_detail(plan: TradingPlanRecord) -> str:
    lines = [
        f"计划日：{plan.trade_date}",
        f"状态：{_STATUS_LABELS.get(plan.status, plan.status)}",
        f"预期情绪：{_EMOTION_LABELS.get(plan.emotion_expected, plan.emotion_expected or '—')}",
        f"计划总仓位：{int(round(plan.max_position_pct * 100))}%",
        f"更新时间：{plan.updated_at.replace('T', ' ')[:16]}",
    ]
    if plan.notes.strip():
        lines.extend(["", "备忘：", plan.notes.strip()])
    lines.extend(["", "观察名单："])
    if not plan.symbols:
        lines.append("（无标的）")
    else:
        for item in plan.symbols:
            modes = "、".join(item.allowed_modes) if item.allowed_modes else "—"
            lines.append(f"- {item.vt_symbol}  模式 {modes}")
            if item.entry_conditions.strip():
                lines.append(f"  入场：{item.entry_conditions.strip()}")
            if item.exit_conditions.strip():
                lines.append(f"  出场：{item.exit_conditions.strip()}")
    return "\n".join(lines)
