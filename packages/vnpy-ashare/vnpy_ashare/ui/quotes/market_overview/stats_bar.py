"""市场页头部统计条：涨跌广度、成交额、恐贪、北向。"""

from __future__ import annotations

from vnpy_ashare.domain.quote_time import format_relative_updated_at

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.quotes.market.market_breadth import MarketBreadthSnapshot
from vnpy_ashare.quotes.market.market_environment import MarketEnvironmentSnapshot, format_north_money_hsgt
from vnpy_ashare.ui.quotes.market_overview.emotion_cycle_chip import EmotionCycleChip
from vnpy_ashare.domain.format import format_amount
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color

# 两市成交额低于 1 万亿时短线赚钱效应偏弱（单位：元）
MARKET_TURNOVER_TRILLION_YUAN = 1e12


def _format_updated_at(raw: str | None) -> str:
    return format_relative_updated_at(raw)


def _format_trade_date(raw: str) -> str:
    text = raw.strip()
    if len(text) == 8 and text.isdigit():
        return f"{text[4:6]}-{text[6:8]}"
    return text


class _StatDivider(QtWidgets.QFrame):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketStatDivider")
        self.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        self.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        self.setFixedWidth(1)


class _StatChip(QtWidgets.QFrame):
    """紧凑指标块：标签 + 主值。"""

    def __init__(self, label: str, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketStatChip")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(1)
        self._label = QtWidgets.QLabel(label)
        self._label.setObjectName("MarketStatChipLabel")
        self._value = QtWidgets.QLabel("—")
        self._value.setObjectName("MarketStatChipValue")
        layout.addWidget(self._label)
        layout.addWidget(self._value)

    def set_value(self, value: str, *, color: str = "", subtitle: str = "") -> None:
        self._value.setText(value)
        if color:
            self._value.setStyleSheet(f"color: {color};")
        else:
            self._value.setStyleSheet("")
        if subtitle:
            self._label.setText(subtitle)
            self._label.setToolTip(subtitle)


class _BreadthRatioBar(QtWidgets.QWidget):
    """涨跌平占比色条。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketBreadthRatioBar")
        self.setFixedHeight(4)
        self._up = 0
        self._down = 0
        self._flat = 0
        self._colors = ("#e74c3c", "#2ecc71", "#888888")

    def set_counts(self, up: int, down: int, flat: int) -> None:
        self._up = max(up, 0)
        self._down = max(down, 0)
        self._flat = max(flat, 0)
        self.update()

    def refresh_theme(self) -> None:
        tokens = theme_manager().tokens()
        self._colors = (
            pct_change_color(1.0, tokens),
            pct_change_color(-1.0, tokens),
            pct_change_color(0.0, tokens),
        )
        self.update()

    def paintEvent(self, _event: QtGui.QPaintEvent) -> None:
        total = self._up + self._down + self._flat
        if total <= 0:
            return
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(0, 0, -1, -1)
        x = rect.x()
        width = rect.width()
        height = rect.height()
        radius = height / 2
        segments = (
            (self._up, self._colors[0]),
            (self._flat, self._colors[2]),
            (self._down, self._colors[1]),
        )
        for count, color in segments:
            if count <= 0:
                continue
            segment_width = max(1, round(width * count / total))
            segment_rect = QtCore.QRectF(x, rect.y(), segment_width, height)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QColor(color))
            painter.drawRoundedRect(segment_rect, radius, radius)
            x += segment_width


class _FearGauge(QtWidgets.QWidget):
    """恐贪指数：数值 + 迷你进度条。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketFearGauge")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(3)

        header = QtWidgets.QHBoxLayout()
        header.setSpacing(6)
        self._title = QtWidgets.QLabel("恐贪指数")
        self._title.setObjectName("MarketStatChipLabel")
        self._value = QtWidgets.QLabel("—")
        self._value.setObjectName("MarketStatChipValue")
        header.addWidget(self._title)
        header.addWidget(self._value)
        header.addStretch(1)
        layout.addLayout(header)

        self._bar = QtWidgets.QProgressBar()
        self._bar.setObjectName("MarketFearGaugeBar")
        self._bar.setRange(0, 100)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)
        layout.addWidget(self._bar)

    def set_snapshot(self, index: float | None, label: str, *, tooltip: str = "") -> None:
        if index is None:
            self._value.setText("—")
            self._bar.setValue(0)
            self.setToolTip(tooltip or "需 Tushare；可运行「Tushare 因子预拉」")
            return
        text = f"{index:.0f}"
        if label:
            text = f"{text} · {label}"
        self._value.setText(text)
        self._bar.setValue(max(0, min(100, round(index))))
        self.setToolTip(tooltip or "A 股恐贪指数（Tushare 行情加权）")


class MarketStatsBar(QtWidgets.QWidget):
    """市场页顶部统计条。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("MarketStatsBar")
        self._last_breadth: MarketBreadthSnapshot | None = None
        self._last_environment: MarketEnvironmentSnapshot | None = None

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(12, 8, 12, 6)
        root.setSpacing(6)

        chips_row = QtWidgets.QHBoxLayout()
        chips_row.setSpacing(6)
        self._emotion_chip = EmotionCycleChip()
        self._up_chip = _StatChip("上涨")
        self._down_chip = _StatChip("下跌")
        self._flat_chip = _StatChip("持平")
        self._limit_up_chip = _StatChip("涨停")
        self._limit_down_chip = _StatChip("跌停")
        self._amount_chip = _StatChip("成交额")
        self._north_chip = _StatChip("北向资金")
        self._fear_gauge = _FearGauge()
        self._updated_label = QtWidgets.QLabel("")
        self._updated_label.setObjectName("MarketStatsUpdated")
        self._updated_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter)

        for widget in (
            self._emotion_chip,
            _StatDivider(),
            self._up_chip,
            self._down_chip,
            self._flat_chip,
            _StatDivider(),
            self._limit_up_chip,
            self._limit_down_chip,
            _StatDivider(),
            self._amount_chip,
            _StatDivider(),
            self._fear_gauge,
            _StatDivider(),
            self._north_chip,
        ):
            chips_row.addWidget(widget)
        chips_row.addStretch(1)
        chips_row.addWidget(self._updated_label)
        root.addLayout(chips_row)

        self._ratio_bar = _BreadthRatioBar(self)
        root.addWidget(self._ratio_bar)

        self.set_loading()

    def set_loading(self) -> None:
        self._updated_label.setText("")
        self._ratio_bar.set_counts(0, 0, 0)
        for chip in (
            self._up_chip,
            self._down_chip,
            self._flat_chip,
            self._limit_up_chip,
            self._limit_down_chip,
            self._amount_chip,
            self._north_chip,
        ):
            chip.set_value("—")
        self._fear_gauge.set_snapshot(None, "")
        self._emotion_chip.set_loading()

    def render_emotion_cycle(self, snapshot) -> None:
        self._emotion_chip.apply_snapshot(snapshot)

    def set_empty(self) -> None:
        self.set_loading()
        self._updated_label.setText("暂无全市场行情")

    def render_breadth(self, breadth: MarketBreadthSnapshot) -> None:
        self._last_breadth = breadth
        tokens = theme_manager().tokens()
        up_color = pct_change_color(1.0, tokens)
        down_color = pct_change_color(-1.0, tokens)
        flat_color = pct_change_color(0.0, tokens)

        self._up_chip.set_value(str(breadth.up), color=up_color)
        self._down_chip.set_value(str(breadth.down), color=down_color)
        self._flat_chip.set_value(str(breadth.flat), color=flat_color)

        limit_tag = "官方" if breadth.limit_source == "tushare" else "近似"
        self._limit_up_chip.set_value(
            str(breadth.limit_up),
            color=up_color,
            subtitle=f"涨停 · {limit_tag}",
        )
        self._limit_down_chip.set_value(
            str(breadth.limit_down),
            color=down_color,
            subtitle=f"跌停 · {limit_tag}",
        )
        self._amount_chip.set_value(
            format_amount(breadth.total_amount),
            color=self._amount_color(breadth.total_amount),
            subtitle=self._amount_subtitle(breadth.total_amount),
        )
        self._amount_chip.setToolTip(self._amount_tooltip(breadth.total_amount))
        self._ratio_bar.set_counts(breadth.up, breadth.down, breadth.flat)
        self._updated_label.setText(_format_updated_at(breadth.updated_at))
        self._render_environment(self._last_environment)

    def _amount_trillion(self, amount: float) -> float:
        if amount <= 0:
            return 0.0
        return amount / MARKET_TURNOVER_TRILLION_YUAN

    def _amount_subtitle(self, amount: float) -> str:
        trillion = self._amount_trillion(amount)
        if trillion <= 0:
            return "成交额"
        return f"成交额 · {trillion:.2f}万亿"

    def _amount_color(self, amount: float) -> str:
        trillion = self._amount_trillion(amount)
        if trillion <= 0:
            return ""
        tokens = theme_manager().tokens()
        if trillion >= 1.0:
            return pct_change_color(1.0, tokens)
        return tokens.semantic_warning

    @staticmethod
    def _amount_tooltip(amount: float) -> str:
        trillion = amount / MARKET_TURNOVER_TRILLION_YUAN if amount > 0 else 0.0
        if trillion >= 1.0:
            return "两市成交额 ≥ 1 万亿，流动性尚可（规则参考）"
        if trillion > 0:
            return "两市成交额 < 1 万亿，短线赚钱效应偏弱（规则参考）"
        return "成交额合计"

    def render_environment(self, env: MarketEnvironmentSnapshot | None) -> None:
        self._last_environment = env
        self._render_environment(env)

    def refresh_theme(self) -> None:
        self._ratio_bar.refresh_theme()
        if self._last_breadth is not None:
            self.render_breadth(self._last_breadth)
        elif self._last_environment is not None:
            self._render_environment(self._last_environment)

    def _render_environment(self, env: MarketEnvironmentSnapshot | None) -> None:
        if env is None or env.fear_greed_index is None:
            self._fear_gauge.set_snapshot(None, "")
        else:
            self._fear_gauge.set_snapshot(env.fear_greed_index, env.fear_greed_label or "")

        if env is None or env.north_money is None:
            self._north_chip.set_value("—")
            self._north_chip.setToolTip("需 Tushare moneyflow_hsgt 缓存")
        else:
            tokens = theme_manager().tokens()
            suffix = f" · {_format_trade_date(env.north_trade_date)}" if env.north_trade_date else ""
            color = pct_change_color(float(env.north_money), tokens) if env.north_money != 0 else tokens.text_muted
            self._north_chip.set_value(
                f"{format_north_money_hsgt(env.north_money)}{suffix}",
                color=color,
            )
            self._north_chip.setToolTip("沪深港通北向净流入（百万元口径）")
