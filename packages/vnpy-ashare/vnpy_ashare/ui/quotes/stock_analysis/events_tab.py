"""个股分析：事件日历 Tab。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.services.stock_events_service import EventsProfile
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.panel_widgets import configure_document_tab_widget, content_card, hint_label, tab_page


def _fmt_amount(value: float | None) -> str:
    if value is None:
        return "—"
    if abs(value) >= 1e8:
        return f"{value / 1e8:.2f}亿"
    if abs(value) >= 1e4:
        return f"{value / 1e4:.1f}万"
    return f"{value:,.0f}"


def _fmt_ratio(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:.2f}%"


class _SimpleTable(QtWidgets.QWidget):
    def __init__(self, headers: list[str], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._table = QtWidgets.QTableWidget(0, len(headers))
        self._table.setHorizontalHeaderLabels(headers)
        configure_data_table(self._table)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._table)

    def fill(self, rows: list[list[str]]) -> None:
        self._table.setRowCount(len(rows))
        for row_idx, values in enumerate(rows):
            for col_idx, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if col_idx > 0:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self._table.setItem(row_idx, col_idx, item)
        self._table.resizeColumnsToContents()


class EventsAnalysisTab(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = hint_label("")
        self._upcoming = hint_label("")

        self._disclosure = _SimpleTable(["报告期", "预约披露", "公告披露", "实际披露"])
        self._dividend = _SimpleTable(["报告期", "方案", "送股", "派息", "除权日", "派息日"])
        self._float = _SimpleTable(["解禁日", "占比", "解禁股数", "股东", "类型"])
        self._ann = _SimpleTable(["日期", "标题"])

        inner = configure_document_tab_widget(QtWidgets.QTabWidget())
        inner.addTab(self._disclosure, "披露")
        inner.addTab(self._dividend, "分红")
        inner.addTab(self._float, "解禁")
        inner.addTab(self._ann, "公告")

        page = tab_page(
            self._status,
            self._upcoming,
            content_card(inner, margins=(4, 4, 4, 4)),
            stretch_index=2,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(page)

    def show_idle(self, message: str = "切换到本 Tab 时加载事件日历") -> None:
        self._status.setText(message)
        self._upcoming.setText("")
        for table in (self._disclosure, self._dividend, self._float, self._ann):
            table.fill([])

    def show_loading(self, message: str = "正在加载事件日历…") -> None:
        self._status.setText(message)
        self._upcoming.setText("")
        for table in (self._disclosure, self._dividend, self._float, self._ann):
            table.fill([])

    def show_profile(self, profile: EventsProfile | None) -> None:
        if profile is None:
            self.show_idle("暂无事件数据")
            return

        if profile.upcoming_hints:
            self._upcoming.setText("近期关注 · " + " · ".join(profile.upcoming_hints))
        else:
            self._upcoming.setText("")

        if profile.message and not any((profile.disclosure, profile.dividends, profile.share_float, profile.announcements)):
            self._status.setText(profile.message)
        else:
            parts = [
                f"披露 {len(profile.disclosure)}",
                f"分红 {len(profile.dividends)}",
                f"解禁 {len(profile.share_float)}",
                f"公告 {len(profile.announcements)}",
            ]
            status = " · ".join(parts)
            if profile.message:
                status += f" · {profile.message}"
            self._status.setText(status)

        self._disclosure.fill(
            [
                [
                    row.get("end_date", "—"),
                    row.get("pre_date") or "—",
                    row.get("ann_date") or "—",
                    row.get("actual_date") or "—",
                ]
                for row in profile.disclosure
            ]
        )
        self._dividend.fill(
            [
                [
                    row.get("end_date", "—"),
                    row.get("div_proc") or "—",
                    f"{row['stk_div']:.4f}" if isinstance(row.get("stk_div"), (int, float)) else "—",
                    f"{row['cash_div']:.4f}" if isinstance(row.get("cash_div"), (int, float)) else "—",
                    row.get("ex_date") or "—",
                    row.get("pay_date") or "—",
                ]
                for row in profile.dividends
            ]
        )
        self._float.fill(
            [
                [
                    row.get("float_date") or "—",
                    _fmt_ratio(row.get("float_ratio")),
                    _fmt_amount(row.get("float_share")),
                    row.get("holder_name") or "—",
                    row.get("share_type") or "—",
                ]
                for row in profile.share_float
            ]
        )
        self._ann.fill([[row.get("ann_date") or "—", row.get("title") or "—"] for row in profile.announcements])
