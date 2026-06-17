"""应用级事件（看盘、回测导航等）。"""

from __future__ import annotations

from typing import Any

from pydantic import ConfigDict, Field

from vnpy_common.domain.base import MutableModel
from vnpy_ashare.screener.run.runner import ScreenerRequest

EVENT_OPEN_BACKTEST = "eOpenBacktest"
EVENT_OPEN_BATCH_BACKTEST = "eOpenBatchBacktest"
EVENT_FILL_SCREENER = "eFillScreener"
EVENT_ASK_AI = "eAskAi"
EVENT_ORB_ATTENTION = "eOrbAttention"
EVENT_AI_ACTION = "eAiAction"


class BacktestRequest(MutableModel):
    """从看盘页跳转策略回测时携带的上下文。"""

    vt_symbol: str = Field(description="VeighNa 合约代码")
    source_page: str = Field(default="", description="来源页面标识")
    name: str = Field(default="", description="证券简称")


class BatchBacktestViewRequest(MutableModel):
    """打开批量回测对比页。"""

    batch_id: str = Field(description="批量回测批次 ID")
    source_page: str = Field(default="", description="来源页面标识")


class FillScreenerRequest(MutableModel):
    """AI 确认流：预填选股页表单（不自动运行）。"""

    request: ScreenerRequest = Field(description="选股请求参数")
    preset_label: str = Field(description="预设方案展示名")
    source_page: str = Field(default="AI", description="来源页面标识")


class FillRecipeRequest(MutableModel):
    """AI 确认流：跳转自动选股页并选中配方（不自动运行）。"""

    recipe_id: str = Field(description="配方 ID")
    trigger_kind: str = Field(default="intraday", description="触发类型")
    top_n: int = Field(default=20, description="输出 Top N")
    source_page: str = Field(default="AI", description="来源页面标识")


class OrbAttentionRequest(MutableModel):
    """通知悬浮球展示轻量提示（如选股完成），不强制展开面板。"""

    source: str = Field(default="", description="提示来源标识")


class AskAiRequest(MutableModel):
    """打开 AI 面板并预填输入框。"""

    prompt: str = Field(description="预填提示词")
    source_page: str = Field(default="", description="来源页面标识")
    use_full_page: bool = Field(default=False, description="是否使用全屏助手")
    new_session: bool = Field(default=False, description="是否新建会话")
    auto_send: bool = Field(default=False, description="是否自动发送")
    session_policy: str = Field(default="resume", description="会话策略：resume | new")
    scene: str = Field(default="", description="场景标识")
    action_id: str = Field(default="", description="关联动作 ID")
    panel_parent: Any = Field(default=None, description="悬浮面板父控件（Qt Widget）")


class AiActionRequest(MutableModel):
    """AI 触发的 UI 写操作（统一入口，内部分发到既有 handler）。"""

    model_config = ConfigDict(
        extra="forbid",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    kind: str = Field(description="动作类型")
    payload: object = Field(description="动作 payload")
    action_id: str = Field(default="", description="动作 ID")
    source: str = Field(default="AI", description="来源标识")
