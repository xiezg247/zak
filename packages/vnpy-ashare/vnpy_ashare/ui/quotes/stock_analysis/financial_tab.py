"""个股分析：财报 Tab（三表 pivot）。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.services.financial_service import FinancialBundle
from vnpy_ashare.storage.financial_store import FinancialSnapshotRow
from vnpy_common.ui.data_table import configure_data_table
from vnpy_common.ui.panel_widgets import content_card, hint_label, section_title, tab_page

_INCOME_ROWS: list[tuple[str, str]] = [
    ("total_revenue", "营业总收入"),
    ("revenue", "营业收入"),
    ("operate_profit", "营业利润"),
    ("total_profit", "利润总额"),
    ("n_income_attr_p", "归母净利润"),
    ("basic_eps", "基本每股收益"),
]

_BALANCE_ROWS: list[tuple[str, str]] = [
    ("total_assets", "资产总计"),
    ("total_liab", "负债合计"),
    ("total_hldr_eqy_exc_min_int", "股东权益合计"),
    ("money_cap", "货币资金"),
    ("accounts_receiv", "应收账款"),
    ("inventories", "存货"),
]

_CASHFLOW_ROWS: list[tuple[str, str]] = [
    ("n_cashflow_act", "经营活动现金流净额"),
    ("n_cashflow_inv_act", "投资活动现金流净额"),
    ("n_cash_flows_fnc_act", "筹资活动现金流净额"),
    ("c_pay_acq_const_fiolta", "购建固定资产等支付现金"),
]

_EXPRESS_ROWS: list[tuple[str, str]] = [
    ("revenue", "营业收入"),
    ("operate_profit", "营业利润"),
    ("n_income", "净利润"),
    ("total_profit", "利润总额"),
    ("diluted_eps", "每股收益"),
]

_FORECAST_ROWS: list[tuple[str, str]] = [
    ("type", "预告类型"),
    ("p_change_min", "净利变动下限%"),
    ("p_change_max", "净利变动上限%"),
    ("net_profit_min", "净利下限"),
    ("net_profit_max", "净利上限"),
    ("summary", "摘要"),
]


def _format_amount(value: Any) -> str:
    if value is None or value == "":
        return "—"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if abs(number) >= 1e8:
        return f"{number / 1e8:.2f}亿"
    if abs(number) >= 1e4:
        return f"{number / 1e4:.2f}万"
    return f"{number:.2f}"


def _format_pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.2f}%"


class _StatementTable(QtWidgets.QWidget):
    def __init__(
        self,
        row_defs: list[tuple[str, str]],
        *,
        empty_hint: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._row_defs = row_defs
        self._empty_hint = empty_hint
        self._table = QtWidgets.QTableWidget(0, 0)
        configure_data_table(self._table)
        self._empty_label = hint_label()
        self._empty_label.setVisible(False)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._empty_label)
        layout.addWidget(self._table)

    def render(self, reports: list[dict[str, Any]], *, show_empty_hint: bool = True) -> None:
        if not reports:
            if self._empty_hint and show_empty_hint:
                self._empty_label.setText(self._empty_hint)
                self._empty_label.setVisible(True)
            else:
                self._empty_label.setVisible(False)
            self._table.setRowCount(0)
            self._table.setColumnCount(0)
            return

        self._empty_label.setVisible(False)
        periods = [str(item.get("end_date") or "") for item in reports if item.get("end_date")]
        self._table.setRowCount(len(self._row_defs))
        self._table.setColumnCount(len(periods) + 1)
        headers = ["科目", *periods]
        self._table.setHorizontalHeaderLabels(headers)

        by_end = {str(item.get("end_date") or ""): item.get("fields") or {} for item in reports}
        for row_index, (field_key, label) in enumerate(self._row_defs):
            self._table.setItem(row_index, 0, QtWidgets.QTableWidgetItem(label))
            for col_index, end_date in enumerate(periods, start=1):
                fields = by_end.get(end_date) or {}
                text = _format_amount(fields.get(field_key))
                self._table.setItem(row_index, col_index, QtWidgets.QTableWidgetItem(text))
        self._table.resizeColumnsToContents()


class FinancialAnalysisTab(QtWidgets.QWidget):
    """财务子 Tab：概览快照 + 三表。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._status = hint_label("暂无财报数据")

        self._snapshot_table = QtWidgets.QTableWidget(0, 0)
        configure_data_table(self._snapshot_table)
        self._snapshot_table.setMaximumHeight(168)

        self._statement_tabs = QtWidgets.QTabWidget()
        self._statement_tabs.setDocumentMode(True)
        self._statement_tabs.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        self._income = _StatementTable(_INCOME_ROWS)
        self._balance = _StatementTable(_BALANCE_ROWS)
        self._cashflow = _StatementTable(_CASHFLOW_ROWS)
        self._express = _StatementTable(
            _EXPRESS_ROWS,
            empty_hint="该公司未披露业绩快报，或尚未同步到本地；可查看「利润表」获取正式财报。",
        )
        self._forecast = _StatementTable(
            _FORECAST_ROWS,
            empty_hint="暂无业绩预告；若公司已发布预告，可点击弹窗底部「刷新」重新拉取。",
        )
        self._statement_tabs.addTab(self._income, "利润表")
        self._statement_tabs.addTab(self._balance, "资产负债表")
        self._statement_tabs.addTab(self._cashflow, "现金流量表")
        self._statement_tabs.addTab(self._express, "业绩快报")
        self._statement_tabs.addTab(self._forecast, "业绩预告")

        statement_card = content_card(self._statement_tabs, margins=(4, 4, 4, 4))
        page = tab_page(
            self._status,
            content_card(
                section_title("关键指标趋势"),
                self._snapshot_table,
            ),
            statement_card,
            stretch_index=2,
        )
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(page)

    def _render_snapshots(self, snapshots: list[FinancialSnapshotRow]) -> None:
        columns = ["报告期", "营收", "归母净利", "ROE", "毛利率", "负债率", "营收同比", "净利同比"]
        self._snapshot_table.setColumnCount(len(columns))
        self._snapshot_table.setHorizontalHeaderLabels(columns)
        self._snapshot_table.setRowCount(len(snapshots))
        for row_index, snap in enumerate(snapshots):
            values = [
                snap.end_date,
                _format_amount(snap.revenue),
                _format_amount(snap.net_income),
                _format_pct(snap.roe),
                _format_pct(snap.gross_margin),
                _format_pct(snap.debt_ratio),
                _format_pct(snap.revenue_yoy),
                _format_pct(snap.net_income_yoy),
            ]
            for col_index, text in enumerate(values):
                item = QtWidgets.QTableWidgetItem(text)
                if col_index > 0:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self._snapshot_table.setItem(row_index, col_index, item)
        self._snapshot_table.resizeColumnsToContents()

    def show_loading(self, message: str = "正在同步财报与估值历史…") -> None:
        self._status.setText(message)
        self._snapshot_table.setRowCount(0)
        self._income.render([], show_empty_hint=False)
        self._balance.render([], show_empty_hint=False)
        self._cashflow.render([], show_empty_hint=False)
        self._express.render([], show_empty_hint=False)
        self._forecast.render([], show_empty_hint=False)

    def show_bundle(self, bundle: FinancialBundle | None, *, sync_message: str = "") -> None:
        if bundle is None:
            self._status.setText(sync_message or "暂无财报数据（请配置 TUSHARE_TOKEN 后刷新）")
            self._snapshot_table.setRowCount(0)
            self._income.render([])
            self._balance.render([])
            self._cashflow.render([])
            self._express.render([])
            self._forecast.render([])
            return

        meta = bundle.sync_meta
        meta_text = ""
        if meta and meta.last_sync_at:
            meta_text = f"最近同步：{meta.last_sync_at}"
            if meta.latest_end_date:
                meta_text += f" · 最新报告期 {meta.latest_end_date}"
        if sync_message:
            meta_text = f"{sync_message} · {meta_text}" if meta_text else sync_message
        self._status.setText(meta_text or "本地财报")

        snapshots = bundle.snapshots
        self._render_snapshots(snapshots)
        reports = bundle.reports
        self._income.render(reports.get("income") or [])
        self._balance.render(reports.get("balancesheet") or [])
        self._cashflow.render(reports.get("cashflow") or [])
        self._express.render(reports.get("express") or [])
        self._forecast.render(reports.get("forecast") or [])
