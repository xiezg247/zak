"""AI 触发的 UI 写操作。"""

from vnpy_ashare.domain.ai.actions import (
    AI_ACTION_ASK_AI,
    AI_ACTION_FILL_RECIPE,
    AI_ACTION_FILL_SCREENER,
    AI_ACTION_OPEN_BACKTEST,
    AI_ACTION_OPEN_BATCH_BACKTEST,
    AI_ACTION_ORB_ATTENTION,
    AiActionKind,
    normalize_ai_action,
    put_ai_action,
    validate_ai_action,
)

__all__ = [
    "AI_ACTION_ASK_AI",
    "AI_ACTION_FILL_RECIPE",
    "AI_ACTION_FILL_SCREENER",
    "AI_ACTION_OPEN_BACKTEST",
    "AI_ACTION_OPEN_BATCH_BACKTEST",
    "AI_ACTION_ORB_ATTENTION",
    "AiActionKind",
    "normalize_ai_action",
    "put_ai_action",
    "validate_ai_action",
]
