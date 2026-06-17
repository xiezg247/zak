"""交易流水复盘对话框（J-05）。"""

from __future__ import annotations

from datetime import datetime, timedelta

from vnpy.trader.ui import QtWidgets
from vnpy.trader.ui import QtWidgets as QtW

from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.trading.journal.prompt import build_journal_prompt
from vnpy_ashare.trading.journal.report import format_journal_entries_csv, load_journal_report


class JournalReportDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("交易流水复盘")
        self.setMinimumSize(420, 320)

        layout = QtWidgets.QVBoxLayout(self)
        range_row = QtWidgets.QHBoxLayout()
        self._days_spin = QtWidgets.QSpinBox(self)
        self._days_spin.setRange(1, 90)
        self._days_spin.setValue(7)
        self._days_spin.setSuffix(" 天")
        refresh_btn = QtWidgets.QPushButton("刷新", self)
        refresh_btn.clicked.connect(self._refresh)
        range_row.addWidget(QtWidgets.QLabel("统计区间", self))
        range_row.addWidget(self._days_spin)
        range_row.addWidget(refresh_btn)
        range_row.addStretch(1)
        layout.addLayout(range_row)

        self._summary = QtWidgets.QLabel("", self)
        self._summary.setWordWrap(True)
        self._summary.setObjectName("SettingsHint")
        layout.addWidget(self._summary)

        self._table = QtWidgets.QTableWidget(self)
        self._table.setColumnCount(2)
        self._table.setHorizontalHeaderLabels(["指标", "数值"])
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table, stretch=1)

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
        close_box.rejected.connect(self.reject)
        layout.addWidget(close_box)

        self._refresh()

    def _refresh(self) -> None:
        end = datetime.now(CHINA_TZ).date()
        start = end - timedelta(days=int(self._days_spin.value()) - 1)
        report = load_journal_report(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        if report.total_entries <= 0:
            self._summary.setText(f"{start.isoformat()} ~ {end.isoformat()}：暂无流水记录")
            self._table.setRowCount(0)
            return
        win_rate = f"{report.win_rate_pct:.1f}%" if report.win_rate_pct is not None else "—"
        pl_ratio = f"{report.profit_loss_ratio:.2f}" if report.profit_loss_ratio is not None else "—"
        on_plan = f"{report.on_plan_ratio_pct:.1f}%" if report.on_plan_ratio_pct is not None else "—"
        violation = f"{report.violation_ratio_pct:.1f}%" if report.violation_ratio_pct is not None else "—"
        self._summary.setText(f"{start.isoformat()} ~ {end.isoformat()} · 已实现合计 {report.realized_pnl_total:+.2f} 元")
        rows = [
            ("流水条数", str(report.total_entries)),
            ("买入 / 卖出", f"{report.buy_count} / {report.sell_count}"),
            ("胜率（已平仓）", win_rate),
            ("盈亏比", pl_ratio),
            ("平均盈利", f"{report.avg_win:+.2f}" if report.avg_win is not None else "—"),
            ("平均亏损", f"{report.avg_loss:+.2f}" if report.avg_loss is not None else "—"),
            ("计划内占比", on_plan),
            ("违规占比", violation),
            ("off_plan", str(report.off_plan_count)),
            ("add_loss", str(report.add_loss_count)),
            ("float_loss_hold", str(report.float_loss_hold_count)),
        ]
        self._table.setRowCount(len(rows))
        for index, (label, value) in enumerate(rows):
            self._table.setItem(index, 0, QtWidgets.QTableWidgetItem(label))
            self._table.setItem(index, 1, QtWidgets.QTableWidgetItem(value))

    def _copy_prompt(self) -> None:

        end = datetime.now(CHINA_TZ).date()
        start = end - timedelta(days=int(self._days_spin.value()) - 1)
        payload = build_journal_prompt(days=int(self._days_spin.value()))
        text = str(payload.get("prompt") or "")
        QtW.QApplication.clipboard().setText(text)
        self._summary.setText(f"已复制复盘 Prompt（{start.isoformat()} ~ {end.isoformat()}）")

    def _export_csv(self) -> None:

        end = datetime.now(CHINA_TZ).date()
        start = end - timedelta(days=int(self._days_spin.value()) - 1)
        csv_text = format_journal_entries_csv(
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        default_name = f"trade_journal_{start.isoformat()}_{end.isoformat()}.csv"
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
