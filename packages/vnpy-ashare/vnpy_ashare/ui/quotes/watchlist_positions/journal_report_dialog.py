"""交易流水复盘对话框（J-05）。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from vnpy.trader.ui import QtWidgets
from vnpy.trader.ui import QtWidgets as QtW

from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.journal.prompt import build_journal_prompt
from vnpy_ashare.trading.journal.report import format_journal_entries_csv, load_journal_report
from vnpy_ashare.ui.quotes.watchlist_positions.trade_journal_manage_view import TradeJournalManageView


def _localize_close_button(box: QtWidgets.QDialogButtonBox) -> None:
    close_btn = box.button(QtWidgets.QDialogButtonBox.StandardButton.Close)
    if close_btn is not None:
        close_btn.setText("关闭")


class JournalReportDialog(QtWidgets.QDialog):
    def __init__(
        self,
        parent: QtWidgets.QWidget | None = None,
        *,
        on_entries_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("交易流水复盘")
        self.setMinimumSize(520, 400)

        layout = QtWidgets.QVBoxLayout(self)
        range_row = QtWidgets.QHBoxLayout()
        self._days_spin = QtWidgets.QSpinBox(self)
        self._days_spin.setRange(1, 90)
        self._days_spin.setValue(7)
        self._days_spin.setSuffix(" 天")
        refresh_btn = QtWidgets.QPushButton("刷新", self)
        refresh_btn.clicked.connect(self._refresh_all)
        range_row.addWidget(QtWidgets.QLabel("统计区间", self))
        range_row.addWidget(self._days_spin)
        range_row.addWidget(refresh_btn)
        range_row.addStretch(1)
        layout.addLayout(range_row)

        self._tabs = QtWidgets.QTabWidget(self)
        self._stats_page = self._build_stats_page()
        self._detail_view = TradeJournalManageView(self, show_range_controls=False)
        if on_entries_changed is not None:
            self._detail_view.entries_changed.connect(on_entries_changed)
        self._tabs.addTab(self._stats_page, "统计")
        self._tabs.addTab(self._detail_view, "流水明细")
        layout.addWidget(self._tabs, stretch=1)

        prompt_btn = QtWidgets.QPushButton("复制复盘 Prompt", self)
        prompt_btn.clicked.connect(self._copy_prompt)
        export_btn = QtWidgets.QPushButton("导出 CSV", self)
        export_btn.clicked.connect(self._export_csv)
        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(prompt_btn)
        btn_row.addWidget(export_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        close_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Close, parent=self)
        _localize_close_button(close_box)
        close_box.rejected.connect(self.reject)
        close_btn = close_box.button(QtWidgets.QDialogButtonBox.StandardButton.Close)
        if close_btn is not None:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(close_box)

        self._refresh_all()

    def _build_stats_page(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget(self)
        page_layout = QtWidgets.QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)
        self._summary = QtWidgets.QLabel("", page)
        self._summary.setWordWrap(True)
        self._summary.setObjectName("SettingsHint")
        page_layout.addWidget(self._summary)
        self._table = QtWidgets.QTableWidget(page)
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["指标", "数值"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        page_layout.addWidget(self._table, stretch=1)
        return page

    def _date_range(self) -> tuple[str, str]:
        end = datetime.now(CHINA_TZ).date()
        start = end - timedelta(days=int(self._days_spin.value()) - 1)
        return start.isoformat(), end.isoformat()

    def _refresh_all(self) -> None:
        start, end = self._date_range()
        self._refresh_stats(start, end)
        self._detail_view.set_date_range(start_date=start, end_date=end)
        self._detail_view.reload()

    def _refresh_stats(self, start: str, end: str) -> None:
        report = load_journal_report(
            start_date=start,
            end_date=end,
        )
        if report.total_entries <= 0:
            self._summary.setText(f"{start} ~ {end}：暂无流水记录")
            self._table.setRowCount(0)
            return
        win_rate = f"{report.win_rate_pct:.1f}%" if report.win_rate_pct is not None else "—"
        pl_ratio = f"{report.profit_loss_ratio:.2f}" if report.profit_loss_ratio is not None else "—"
        in_mode_win_rate = f"{report.in_mode_win_rate_pct:.1f}%" if report.in_mode_win_rate_pct is not None else "—"
        in_mode_pl = f"{report.in_mode_profit_loss_ratio:.2f}" if report.in_mode_profit_loss_ratio is not None else "—"
        in_mode_pnl = f"{report.in_mode_realized_pnl_total:+.2f}"
        on_plan = f"{report.on_plan_ratio_pct:.1f}%" if report.on_plan_ratio_pct is not None else "—"
        violation = f"{report.violation_ratio_pct:.1f}%" if report.violation_ratio_pct is not None else "—"
        self._summary.setText(f"{start} ~ {end} · 已实现合计 {report.realized_pnl_total:+.2f} 元")
        rows = [
            ("流水条数", str(report.total_entries)),
            ("买入 / 卖出", f"{report.buy_count} / {report.sell_count}"),
            ("胜率（已平仓）", win_rate),
            ("盈亏比", pl_ratio),
            ("模式内胜率", in_mode_win_rate),
            ("模式内盈亏比", in_mode_pl),
            ("模式内已实现", in_mode_pnl),
            ("平均盈利", f"{report.avg_win:+.2f}" if report.avg_win is not None else "—"),
            ("平均亏损", f"{report.avg_loss:+.2f}" if report.avg_loss is not None else "—"),
            ("计划内占比", on_plan),
            ("违规占比", violation),
            ("off_plan", str(report.off_plan_count)),
            ("add_loss", str(report.add_loss_count)),
            ("float_loss_hold", str(report.float_loss_hold_count)),
        ]
        for item in report.mode_breakdown:
            label = f"mode·{item.mode}"
            value = f"卖 {item.sell_count} · 胜率 {item.win_rate_pct or 0:.0f}% · 盈亏比 {item.profit_loss_ratio or 0:.1f}"
            rows.append((label, value))
        self._table.setRowCount(len(rows))
        for index, (label, value) in enumerate(rows):
            self._table.setItem(index, 0, QtWidgets.QTableWidgetItem(label))
            self._table.setItem(index, 1, QtWidgets.QTableWidgetItem(value))

    def _copy_prompt(self) -> None:
        start, end = self._date_range()
        payload = build_journal_prompt(days=int(self._days_spin.value()))
        text = str(payload.get("prompt") or "")
        QtW.QApplication.clipboard().setText(text)
        self._summary.setText(f"已复制复盘 Prompt（{start} ~ {end}）")

    def _export_csv(self) -> None:
        start, end = self._date_range()
        csv_text = format_journal_entries_csv(
            start_date=start,
            end_date=end,
        )
        default_name = f"trade_journal_{start}_{end}.csv"
        path, _ = QtW.QFileDialog.getSaveFileName(
            self,
            "导出交易流水",
            default_name,
            "CSV (*.csv)",
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig") as handle:
            handle.write(csv_text)
        self._summary.setText(f"已导出 CSV：{path}")
