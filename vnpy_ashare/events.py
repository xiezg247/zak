"""应用级事件（看盘、回测导航等）。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.screener.runner import ScreenerRequest

EVENT_OPEN_BACKTEST = "eOpenBacktest"
EVENT_OPEN_BATCH_BACKTEST = "eOpenBatchBacktest"
EVENT_FILL_SCREENER = "eFillScreener"
EVENT_ASK_AI = "eAskAi"


@dataclass
class BacktestRequest:
    """从看盘页跳转策略回测时携带的上下文。"""

    vt_symbol: str
    source_page: str = ""
    name: str = ""


@dataclass
class BatchBacktestViewRequest:
    """打开批量回测对比页。"""

    batch_id: str
    source_page: str = ""


@dataclass
class FillScreenerRequest:
    """AI 确认流：预填选股页表单（不自动运行）。"""

    request: ScreenerRequest
    preset_label: str
    source_page: str = "AI"


@dataclass
class AskAiRequest:
    """打开 AI 面板并预填输入框。"""

    prompt: str
    source_page: str = ""
    use_full_page: bool = False
