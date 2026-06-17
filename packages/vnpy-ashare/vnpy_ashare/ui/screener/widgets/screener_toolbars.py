"""选股页工具栏：主操作条 + 结果区操作条。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets


def screener_toolbar_separator() -> QtWidgets.QFrame:
    sep = QtWidgets.QFrame()
    sep.setObjectName("ToolbarSeparator")
    sep.setFrameShape(QtWidgets.QFrame.Shape.VLine)
    sep.setFixedWidth(1)
    sep.setFixedHeight(22)
    return sep


class ScreenerResultActionBar(QtWidgets.QWidget):
    """结果表上方操作条：有结果时展示，无结果时隐藏。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ScreenerResultActionBar")
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.setSpacing(8)

        self.select_all_btn = QtWidgets.QPushButton("全 选")
        self.select_all_btn.setObjectName("SecondaryButton")
        layout.addWidget(self.select_all_btn)

        self.add_watchlist_btn = QtWidgets.QPushButton("加入自选")
        self.add_watchlist_btn.setObjectName("SecondaryButton")
        layout.addWidget(self.add_watchlist_btn)

        self.add_observation_group_btn = QtWidgets.QPushButton("加入观察组")
        self.add_observation_group_btn.setObjectName("SecondaryButton")
        self.add_observation_group_btn.setToolTip("加入自选并写入「短线观察」分组")
        layout.addWidget(self.add_observation_group_btn)

        self.download_btn = QtWidgets.QPushButton("下载日K")
        self.download_btn.setObjectName("SecondaryButton")
        layout.addWidget(self.download_btn)

        layout.addWidget(screener_toolbar_separator())

        self.backtest_btn = QtWidgets.QPushButton("策略回测")
        self.backtest_btn.setObjectName("SecondaryButton")
        layout.addWidget(self.backtest_btn)

        self.batch_backtest_btn = QtWidgets.QPushButton("批量回测")
        self.batch_backtest_btn.setObjectName("SecondaryButton")
        layout.addWidget(self.batch_backtest_btn)

        self.reference_peer_btn = QtWidgets.QPushButton("找同类")
        self.reference_peer_btn.setObjectName("SecondaryButton")
        self.reference_peer_btn.setToolTip("以勾选的单只标的为标杆，筛选相似股票")
        layout.addWidget(self.reference_peer_btn)

        layout.addStretch()
        self.hide()

    def set_has_results(self, has_results: bool) -> None:
        self.setVisible(has_results)
