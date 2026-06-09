"""应用级事件（看盘、回测导航等）。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.screener.runner import ScreenerRequest

EVENT_OPEN_BACKTEST = "eOpenBacktest"
EVENT_OPEN_BATCH_BACKTEST = "eOpenBatchBacktest"
EVENT_FILL_SCREENER = "eFillScreener"
EVENT_ASK_AI = "eAskAi"
EVENT_ORB_ATTENTION = "eOrbAttention"
EVENT_AI_ACTION = "eAiAction"


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
class OrbAttentionRequest:
    """通知悬浮球展示轻量提示（如选股完成），不强制展开面板。"""

    source: str = ""


@dataclass
class AskAiRequest:
    """打开 AI 面板并预填输入框。"""

    prompt: str
    source_page: str = ""
    use_full_page: bool = False
    new_session: bool = False
    auto_send: bool = False
    session_policy: str = "resume"  # resume | new
    scene: str = ""
    action_id: str = ""


@dataclass
class AiActionRequest:
    """AI 触发的 UI 写操作（统一入口，内部分发到既有 handler）。"""

    kind: str
    payload: object
    action_id: str = ""
    source: str = "AI"
