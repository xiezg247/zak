"""个股分析：概览（本地技术面 + 策略信号）。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
from vnpy_common.ui.panel_widgets import MetricTile, content_card, hint_label, section_title, tile_grid
from vnpy_common.ui.scroll_area import frameless_scroll_area
from vnpy_common.ui.theme import theme_manager
from vnpy_common.ui.theme.market_colors import pct_change_color


def _fmt(value: float | None, *, digits: int = 2, suffix: str = "") -> str:
    if value is None:
        return "—"
    return f"{value:.{digits}f}{suffix}"


class OverviewAnalysisPanel(QtWidgets.QWidget):
    """概览：本地指标 + 策略信号；问小达/通达信走 AI 助手按需拉取。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._local_tiles = {
            "close": MetricTile("收盘", subtitle="截至日期"),
            "ma": MetricTile("均线排列"),
            "volume": MetricTile("5日量比"),
            "ret20": MetricTile("20日涨跌"),
            "rs": MetricTile("相对沪深300", subtitle="20日超额"),
        }
        self._signal_tiles = {
            "signal": MetricTile("策略信号", subtitle="双均线"),
            "strength": MetricTile("信号强度"),
            "ref_buy": MetricTile("参考买点"),
            "ref_sell": MetricTile("参考卖点"),
        }

        self._ai_hint = hint_label("问小达 / 通达信多维诊断请使用底部「问 AI 解读」，AI 将按需调用 MCP 工具。")

        self._technical_body = QtWidgets.QLabel("")
        self._technical_body.setWordWrap(True)
        self._technical_body.setObjectName("DiagnoseBody")

        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._ai_hint)
        layout.addWidget(
            content_card(
                section_title("本地指标"),
                tile_grid(self._local_tiles, columns=3),
                margins=(8, 8, 8, 8),
            )
        )
        layout.addWidget(
            content_card(
                section_title("策略信号"),
                tile_grid(self._signal_tiles, columns=2),
                margins=(8, 8, 8, 8),
            )
        )
        layout.addWidget(
            content_card(
                section_title("技术面详情"),
                frameless_scroll_area(self._technical_body),
            ),
            stretch=1,
        )

    def show_loading(self) -> None:
        for tile in self._local_tiles.values():
            tile.set_value("…")
        for tile in self._signal_tiles.values():
            tile.set_value("…")
        self._technical_body.setText("正在分析本地技术面…")

    def show_payload(
        self,
        *,
        technical: dict[str, Any] | None = None,
        technical_text: str = "",
        relative_returns: dict[str, float | None] | None = None,
        signal: SignalSnapshot | None = None,
    ) -> None:
        technical = technical or {}
        relative_returns = relative_returns or {}
        tokens = theme_manager().tokens()

        if technical.get("error"):
            for tile in self._local_tiles.values():
                tile.set_value("—")
        elif technical.get("warnings") and technical.get("last_close") is None:
            for tile in self._local_tiles.values():
                tile.set_value("—")
        else:
            as_of = str(technical.get("as_of") or "—")
            last_close = technical.get("last_close")
            self._local_tiles["close"].set_value(
                _fmt(last_close if isinstance(last_close, (int, float)) else None),
                subtitle=as_of,
            )
            self._local_tiles["ma"].set_value(str(technical.get("ma_alignment") or "—"))
            vol = technical.get("volume_ratio_5d")
            self._local_tiles["volume"].set_value(_fmt(vol if isinstance(vol, (int, float)) else None))
            ret_20 = relative_returns.get("ret_20d")
            if ret_20 is None:
                period = technical.get("period_return") or {}
                ret_20 = period.get("return_pct")
            ret_color = pct_change_color(ret_20 if isinstance(ret_20, (int, float)) else 0, tokens)
            self._local_tiles["ret20"].set_value(
                f"{ret_20:+.2f}%" if isinstance(ret_20, (int, float)) else "—",
                color=ret_color if isinstance(ret_20, (int, float)) else "",
            )
            rs = relative_returns.get("rs_20d")
            if rs is None and signal is not None:
                rs = signal.relative_index_pct
            rs_color = pct_change_color(rs if isinstance(rs, (int, float)) else 0, tokens)
            self._local_tiles["rs"].set_value(
                f"{rs:+.2f}%" if isinstance(rs, (int, float)) else "—",
                color=rs_color if isinstance(rs, (int, float)) else "",
            )

        if signal is None or signal.signal == "na":
            self._signal_tiles["signal"].set_value("—", subtitle="暂无有效信号")
            self._signal_tiles["strength"].set_value("—")
            self._signal_tiles["ref_buy"].set_value("—")
            self._signal_tiles["ref_sell"].set_value("—")
        else:
            self._signal_tiles["signal"].set_value(
                signal.signal_label,
                subtitle=signal.signal_date or "—",
            )
            strength = signal.strength
            self._signal_tiles["strength"].set_value(
                f"{strength:.0f}" if strength is not None else "—",
            )
            ref_buy = signal.ref_buy_price
            ref_sell = signal.ref_sell_price
            self._signal_tiles["ref_buy"].set_value(
                f"{ref_buy:.2f}" if ref_buy is not None else "—",
            )
            self._signal_tiles["ref_sell"].set_value(
                f"{ref_sell:.2f}" if ref_sell is not None else "—",
            )

        self._technical_body.setText(technical_text or "暂无本地技术面")
