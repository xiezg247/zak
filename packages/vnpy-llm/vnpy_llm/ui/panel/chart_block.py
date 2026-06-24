"""AI 聊天内嵌迷你图块。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore, QtGui, QtWidgets

from vnpy_ashare.ui.components.ai_chart_gallery import AiMiniChartPanel, chart_gallery_stylesheet
from vnpy_common.ai.protocol import AiChartSpec
from vnpy_common.ui.theme.manager import theme_manager

if TYPE_CHECKING:
    from vnpy_llm.ui.panel.symbol_actions import AssistantSymbolActions


def chart_blocks_available() -> bool:
    try:
        from vnpy_ashare.ui.components.ai_mini_candle import AiMiniCandleChart  # noqa: F401

        return True
    except ImportError:
        return False


def _hint_text(spec: AiChartSpec) -> str:
    if spec.source_tool == "get_backtest_result" or spec.chart_key.startswith("backtest:"):
        return "点击查看回测页 →"
    return "点击查看完整分析 →"


class AiMiniChartBlock(AiMiniChartPanel):
    """AI 聊天气泡内迷你图（带跳转动作）。"""

    def __init__(
        self,
        spec: AiChartSpec,
        *,
        symbol_actions: AssistantSymbolActions | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self._symbol_actions = symbol_actions
        super().__init__(spec, hint=_hint_text(spec), parent=parent)
        self.setObjectName("AiMiniChartBlock")
        theme_manager().bind_stylesheet(self, extra=_build_chart_block_stylesheet)

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self._open_target()
            event.accept()
            return
        super().mousePressEvent(event)

    def _open_target(self) -> None:
        if self._symbol_actions is None:
            return
        if self._spec.source_tool == "get_backtest_result" or self._spec.chart_key.startswith("backtest:"):
            self._symbol_actions.open_backtest(self._spec.symbol, name=self._spec.name)
            return
        self._symbol_actions.open_analysis(self._spec.symbol, name=self._spec.name)


def _build_chart_block_stylesheet(tokens) -> str:
    return str(chart_gallery_stylesheet(tokens).replace("AiMiniChartPanel", "AiMiniChartBlock"))
