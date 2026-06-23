"""工作台市场快照（仅读内存缓存，不发起网络请求）。"""

from __future__ import annotations

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.market.emotion_cycle_cache import peek_emotion_cycle_snapshot
from vnpy_ashare.quotes.market.market_overview_cache import peek_market_overview_data
from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_chip import EmotionCycleChip


class HomeMarketPeekStrip(QtWidgets.QWidget):
    """首屏紧凑市场条：有缓存则展示，无缓存则提示去市场页。"""

    open_market_requested = QtCore.Signal()

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeMarketPeek")

        row = QtWidgets.QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self._emotion_chip = EmotionCycleChip(self)
        self._breadth_label = QtWidgets.QLabel("")
        self._breadth_label.setObjectName("HomeMarketPeekBreadth")
        self._hint = QtWidgets.QLabel("")
        self._hint.setObjectName("HomeSummaryHint")
        self._hint.setWordWrap(True)

        self._market_btn = QtWidgets.QPushButton("市场概览")
        self._market_btn.setObjectName("SecondaryButton")
        self._market_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        self._market_btn.clicked.connect(self.open_market_requested.emit)

        row.addWidget(self._emotion_chip)
        row.addWidget(self._breadth_label)
        row.addWidget(self._hint, stretch=1)
        row.addStretch(1)
        row.addWidget(self._market_btn)

        self._emotion_chip.hide()
        self._breadth_label.hide()

    def refresh_from_cache(self) -> None:
        intraday = is_ashare_trading_session()
        peeked = peek_market_overview_data(intraday=intraday)
        if peeked is None and intraday:
            peeked = peek_market_overview_data(intraday=False)

        emotion_ttl = 30.0 if intraday else 86400.0
        emotion = peek_emotion_cycle_snapshot(max_age_sec=emotion_ttl)

        if emotion is not None:
            self._emotion_chip.apply_snapshot(emotion)
            self._emotion_chip.show()
        else:
            self._emotion_chip.hide()

        breadth = peeked.breadth if peeked is not None else None
        if breadth is not None:
            self._breadth_label.setText(
                f"涨 {breadth.up} · 跌 {breadth.down} · 平 {breadth.flat}"
            )
            self._breadth_label.show()
        else:
            self._breadth_label.hide()

        if peeked is not None or emotion is not None:
            self._hint.setText("以下为缓存快照；完整指数与行业榜请打开市场页")
        else:
            self._hint.setText("暂无市场缓存；打开市场页后将自动加载概览")
