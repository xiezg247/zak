"""Playbook AI 上下文测试。"""

from __future__ import annotations

from vnpy_ashare.ai.context.enrichment import build_page_quick_actions
from vnpy_ashare.ai.context.playbook import build_discipline_one_liner_prompt, build_playbook_extra
from vnpy_ashare.services.trading_playbook import build_home_playbook_status
from vnpy_common.ai.protocol import AiContextData


def test_playbook_ai_prompt_and_actions() -> None:
    prompt = build_discipline_one_liner_prompt()
    assert "40 字" in prompt
    extra = build_playbook_extra(build_home_playbook_status(None))
    assert "Playbook" in extra
    actions = build_page_quick_actions(AiContextData(page="交易体系"))
    assert any(item.id == "discipline_one_liner" for item in actions)
