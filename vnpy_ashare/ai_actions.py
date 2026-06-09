"""AI 触发的 UI 写操作：统一 Event 入口与分发辅助。"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal

from vnpy.event import Event, EventEngine

from vnpy_ashare.events import (
    EVENT_AI_ACTION,
    AiActionRequest,
    AskAiRequest,
    BacktestRequest,
    BatchBacktestViewRequest,
    FillScreenerRequest,
    OrbAttentionRequest,
)

AI_ACTION_FILL_SCREENER = "fill_screener"
AI_ACTION_ASK_AI = "ask_ai"
AI_ACTION_OPEN_BACKTEST = "open_backtest"
AI_ACTION_OPEN_BATCH_BACKTEST = "open_batch_backtest"
AI_ACTION_ORB_ATTENTION = "orb_attention"

AiActionKind = Literal[
    "fill_screener",
    "ask_ai",
    "open_backtest",
    "open_batch_backtest",
    "orb_attention",
]

_PAYLOAD_TYPES: dict[str, type[object]] = {
    AI_ACTION_FILL_SCREENER: FillScreenerRequest,
    AI_ACTION_ASK_AI: AskAiRequest,
    AI_ACTION_OPEN_BACKTEST: BacktestRequest,
    AI_ACTION_OPEN_BATCH_BACKTEST: BatchBacktestViewRequest,
    AI_ACTION_ORB_ATTENTION: OrbAttentionRequest,
}


def validate_ai_action(data: AiActionRequest) -> None:
    """校验 action kind 与 payload 类型是否匹配。"""
    expected = _PAYLOAD_TYPES.get(data.kind)
    if expected is None:
        raise ValueError(f"未知 AI 动作: {data.kind}")
    if not isinstance(data.payload, expected):
        raise TypeError(
            f"AI 动作 {data.kind} 需要 {expected.__name__}，"
            f"实际为 {type(data.payload).__name__}",
        )


def normalize_ai_action(data: AiActionRequest) -> AiActionRequest:
    """校验并规范化 payload（如合并 action_id）。"""
    validate_ai_action(data)
    if data.kind != AI_ACTION_ASK_AI or not data.action_id:
        return data
    payload = data.payload
    assert isinstance(payload, AskAiRequest)
    if payload.action_id:
        return data
    return replace(data, payload=replace(payload, action_id=data.action_id))


def put_ai_action(
    event_engine: EventEngine,
    kind: AiActionKind,
    payload: object,
    *,
    action_id: str = "",
    source: str = "AI",
) -> None:
    """从任意线程投递 AI 写操作到 GUI 主线程。"""
    data = AiActionRequest(
        kind=kind,
        payload=payload,
        action_id=action_id.strip(),
        source=source,
    )
    validate_ai_action(data)
    event_engine.put(Event(EVENT_AI_ACTION, data))
