"""AI UI：全屏页与悬浮球动作。"""

from vnpy_ashare.ai.ui.floating_actions import (
    build_quick_actions_for_panel,
    enrich_context_with_actions,
    orb_tooltip_text,
    scene_label_from_context,
)
from vnpy_ashare.ai.ui.page import AiPageWidget

__all__ = [
    "AiPageWidget",
    "build_quick_actions_for_panel",
    "enrich_context_with_actions",
    "orb_tooltip_text",
    "scene_label_from_context",
]
