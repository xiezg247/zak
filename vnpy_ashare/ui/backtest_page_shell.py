"""策略回测页布局（A 股终端风格）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtWidgets

if TYPE_CHECKING:
    from vnpy_ashare.ui.backtest_widget import BacktesterWidget


def _toolbar_separator() -> QtWidgets.QFrame:
    sep = QtWidgets.QFrame()
    sep.setObjectName("ToolbarSeparator")
    sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
    sep.setFixedHeight(22)
    return sep


def _add_more_menu(
    toolbar: QtWidgets.QHBoxLayout,
    actions: list[tuple[str, QtWidgets.QPushButton]],
) -> None:
    visible = [(label, btn) for label, btn in actions if btn is not None]
    if not visible:
        return
    menu_btn = QtWidgets.QPushButton("更多 ▾")
    menu_btn.setObjectName("SecondaryButton")
    menu = QtWidgets.QMenu(menu_btn)
    for label, action_btn in visible:
        menu.addAction(label, action_btn.click)
    menu_btn.setMenu(menu)
    toolbar.addWidget(menu_btn)


class BacktestPageShell:
    """构建策略回测页：左参数 / 右图表 + 统计 + 日志。"""

    def __init__(self, page: BacktesterWidget) -> None:
        self._page = page

    def build(self) -> None:
        page = self._page

        root = QtWidgets.QVBoxLayout(page)
        root.setContentsMargins(16, 12, 16, 12)
        root.setSpacing(10)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("策略回测")
        title.setObjectName("PageTitle")
        hint = QtWidgets.QLabel("A 股现货 · T+1 · 整手 · 仅做多")
        hint.setObjectName("PageHint")
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(hint)
        header.addStretch()
        if hasattr(page, "strategy_guide_button"):
            header.addWidget(page.strategy_guide_button)
        if hasattr(page, "ask_ai_button"):
            header.addWidget(page.ask_ai_button)
        root.addLayout(header)

        toolbar = QtWidgets.QHBoxLayout()
        toolbar.setSpacing(8)
        page.run_button.setObjectName("PrimaryRunButton")
        toolbar.addWidget(page.run_button)
        toolbar.addWidget(_toolbar_separator())
        for btn in (
            page.trade_button,
            page.order_button,
            page.daily_button,
            page.candle_button,
        ):
            btn.setObjectName("SecondaryButton")
            toolbar.addWidget(btn)
        toolbar.addStretch()
        _add_more_menu(
            toolbar,
            [
                ("下载数据", page.download_button),
                ("参数优化", page.optimization_button),
                ("优化结果", page.result_button),
                ("代码编辑", page.edit_button),
                ("策略重载", page.reload_button),
            ],
        )
        root.addLayout(toolbar)

        main_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        main_split.setChildrenCollapsible(False)
        main_split.setHandleWidth(1)

        form_panel = QtWidgets.QWidget()
        form_panel.setObjectName("BacktestFormPanel")
        form_panel.setMinimumWidth(260)
        form_panel.setMaximumWidth(320)
        form_outer = QtWidgets.QVBoxLayout(form_panel)
        form_outer.setContentsMargins(0, 0, 8, 0)
        form_outer.setSpacing(0)

        form_box = QtWidgets.QGroupBox("回测参数")
        form_box.setObjectName("BacktestFormBox")
        form = QtWidgets.QFormLayout(form_box)
        form.setSpacing(8)
        form.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
        page._install_strategy_guide(form)
        form.addRow("股票代码", page.symbol_line)
        form.addRow("K 线周期", page.interval_combo)
        form.addRow("开始日期", page.start_date_edit)
        form.addRow("结束日期", page.end_date_edit)
        form.addRow("手续费率", page.rate_line)
        form.addRow("交易滑点", page.slippage_line)
        form.addRow("每股乘数", page.size_line)
        form.addRow("价格跳动", page.pricetick_line)
        form.addRow("回测资金", page.capital_line)
        form_outer.addWidget(form_box)
        form_outer.addStretch()
        main_split.addWidget(form_panel)

        right_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        right_split.setChildrenCollapsible(False)
        right_split.setHandleWidth(1)

        chart_frame = QtWidgets.QWidget()
        chart_frame.setObjectName("BacktestChartFrame")
        chart_layout = QtWidgets.QVBoxLayout(chart_frame)
        chart_layout.setContentsMargins(0, 0, 0, 0)
        chart_layout.addWidget(page.chart)
        right_split.addWidget(chart_frame)

        bottom_split = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        bottom_split.setChildrenCollapsible(False)
        bottom_split.setHandleWidth(1)
        page.statistics_monitor.setObjectName("BacktestStatisticsTable")
        page.log_monitor.setObjectName("BacktestLogView")
        page.log_monitor.setReadOnly(True)
        bottom_split.addWidget(page.statistics_monitor)
        bottom_split.addWidget(page.log_monitor)
        bottom_split.setStretchFactor(0, 3)
        bottom_split.setStretchFactor(1, 2)
        right_split.addWidget(bottom_split)

        right_split.setStretchFactor(0, 3)
        right_split.setStretchFactor(1, 2)
        main_split.addWidget(right_split)
        main_split.setStretchFactor(0, 0)
        main_split.setStretchFactor(1, 1)
        main_split.setSizes([280, 900])
        right_split.setSizes([420, 260])
        bottom_split.setSizes([360, 240])

        root.addWidget(main_split, stretch=1)
