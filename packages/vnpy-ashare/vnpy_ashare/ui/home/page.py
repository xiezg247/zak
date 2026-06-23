"""工作台首屏：快捷入口 + 本地摘要（不拉 TickFlow）。"""

from __future__ import annotations

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.app.engine_access import get_position_service, get_watchlist_service
from vnpy_ashare.domain.time.market_hours import ashare_market_phase_label
from vnpy_ashare.scheduler.config import load_scheduler_config
from vnpy_ashare.ui.home.market_peek import HomeMarketPeekStrip
from vnpy_common.ui.theme.manager import theme_manager

_QUICK_LINKS: tuple[tuple[str, str], ...] = (
    ("watchlist", "自选"),
    ("radar", "雷达"),
    ("sector_flow", "板块资金"),
    ("screener", "选股"),
)


class _SummaryCard(QtWidgets.QFrame):
    def __init__(self, title: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketStatChip")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(4)
        self._title = QtWidgets.QLabel(title)
        self._title.setObjectName("MarketStatChipLabel")
        self._value = QtWidgets.QLabel("—")
        self._value.setObjectName("MarketStatChipValue")
        self._hint = QtWidgets.QLabel("")
        self._hint.setObjectName("HomeSummaryHint")
        self._hint.setWordWrap(True)
        layout.addWidget(self._title)
        layout.addWidget(self._value)
        layout.addWidget(self._hint)

    def apply(self, value: str, hint: str = "") -> None:
        self._value.setText(value)
        self._hint.setText(hint)
        self._hint.setVisible(bool(hint))


class HomePageWidget(QtWidgets.QWidget):
    """轻量首屏：不加载 QuotesPage，不自动请求市场 API。"""

    def __init__(self, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__()
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.setObjectName("HomeRoot")

        scroll = QtWidgets.QScrollArea(self)
        scroll.setObjectName("HomeScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        body = QtWidgets.QWidget()
        body.setObjectName("HomeBody")
        root = QtWidgets.QVBoxLayout(body)
        root.setContentsMargins(16, 16, 16, 24)
        root.setSpacing(16)

        header = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("工作台")
        title.setObjectName("HomeTitle")
        phase = QtWidgets.QLabel(ashare_market_phase_label())
        phase.setObjectName("HomePhaseLabel")
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(phase)
        root.addLayout(header)

        self._market_peek = HomeMarketPeekStrip(body)
        self._market_peek.open_market_requested.connect(lambda: self._open_page("market"))
        root.addWidget(self._market_peek)

        quick_row = QtWidgets.QHBoxLayout()
        quick_row.setSpacing(10)
        for key, label in _QUICK_LINKS:
            btn = QtWidgets.QPushButton(label)
            btn.setObjectName("SecondaryButton")
            btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
            btn.clicked.connect(lambda _checked=False, page_key=key: self._open_page(page_key))
            quick_row.addWidget(btn)
        quick_row.addStretch(1)
        root.addLayout(quick_row)

        summary_row = QtWidgets.QHBoxLayout()
        summary_row.setSpacing(12)
        self._watchlist_card = _SummaryCard("自选池")
        self._position_card = _SummaryCard("持仓")
        self._scheduler_card = _SummaryCard("定时任务")
        for card in (self._watchlist_card, self._position_card, self._scheduler_card):
            summary_row.addWidget(card, stretch=1)
        root.addLayout(summary_row)
        root.addStretch(1)

        scroll.setWidget(body)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        theme_manager().bind_stylesheet(self)

    def activate(self) -> None:
        self._market_peek.refresh_from_cache()
        self._refresh_summary_cards()

    def deactivate(self) -> None:
        pass

    def _refresh_summary_cards(self) -> None:
        watchlist = get_watchlist_service(self.main_engine)
        if watchlist is not None:
            count = watchlist.count()
            self._watchlist_card.apply(f"{count} 只", "进入自选查看行情与信号")
        else:
            self._watchlist_card.apply("—", "自选服务未就绪")

        position = get_position_service(self.main_engine)
        if position is not None:
            count = position.count()
            self._position_card.apply(f"{count} 笔", "进入自选 · 持仓区管理")
        else:
            self._position_card.apply("—", "持仓服务未就绪")

        cfg = load_scheduler_config()
        enabled = sum(
            1
            for name in cfg.model_fields
            if getattr(getattr(cfg, name), "enabled", False)
        )
        self._scheduler_card.apply(
            f"{enabled} 项已启用",
            "后台 → 定时任务 可查看详情（窗口就绪后自动启动）",
        )

    def _open_page(self, key: str) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "navigate_to_page"):
            return
        host.navigate_to_page(key)

    def _find_main_window(self) -> QtWidgets.QWidget | None:
        widget: QtWidgets.QWidget | None = self
        while widget is not None:
            if hasattr(widget, "navigate_to_page"):
                return widget
            widget = widget.parentWidget()
        return None
