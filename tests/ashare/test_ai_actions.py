"""AI 写操作统一 Event 测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from vnpy.event import Event

from vnpy_ashare.app.events import (
    EVENT_AI_ACTION,
    AiActionRequest,
    AskAiRequest,
    FillScreenerRequest,
    OrbAttentionRequest,
)
from vnpy_ashare.domain.ai_actions import (
    AI_ACTION_ASK_AI,
    AI_ACTION_FILL_SCREENER,
    AI_ACTION_ORB_ATTENTION,
    normalize_ai_action,
    put_ai_action,
    validate_ai_action,
)
from vnpy_ashare.screener.run.runner import ScreenerRequest


class AiActionsTests(unittest.TestCase):
    def test_validate_fill_screener(self) -> None:
        payload = FillScreenerRequest(
            request=ScreenerRequest(preset="涨幅榜"),
            preset_label="涨幅榜",
        )
        validate_ai_action(AiActionRequest(kind=AI_ACTION_FILL_SCREENER, payload=payload))

    def test_validate_rejects_mismatched_payload(self) -> None:
        with self.assertRaises(TypeError):
            validate_ai_action(
                AiActionRequest(
                    kind=AI_ACTION_FILL_SCREENER,
                    payload=AskAiRequest(prompt="hi"),
                )
            )

    def test_normalize_merges_action_id_into_ask_ai(self) -> None:
        payload = AskAiRequest(prompt="诊断", source_page="自选")
        data = AiActionRequest(
            kind=AI_ACTION_ASK_AI,
            payload=payload,
            action_id="diagnose_full",
        )
        normalized = normalize_ai_action(data)
        assert isinstance(normalized.payload, AskAiRequest)
        self.assertEqual(normalized.payload.action_id, "diagnose_full")

    def test_normalize_keeps_existing_ask_ai_action_id(self) -> None:
        payload = AskAiRequest(prompt="诊断", action_id="existing")
        data = AiActionRequest(
            kind=AI_ACTION_ASK_AI,
            payload=payload,
            action_id="diagnose_full",
        )
        normalized = normalize_ai_action(data)
        assert isinstance(normalized.payload, AskAiRequest)
        self.assertEqual(normalized.payload.action_id, "existing")

    def test_put_ai_action_emits_event(self) -> None:
        engine = MagicMock()
        put_ai_action(
            engine,
            AI_ACTION_ORB_ATTENTION,
            OrbAttentionRequest(source="screener"),
            action_id="screen_done",
        )
        engine.put.assert_called_once()
        event = engine.put.call_args[0][0]
        self.assertIsInstance(event, Event)
        self.assertEqual(event.type, EVENT_AI_ACTION)
        assert isinstance(event.data, AiActionRequest)
        self.assertEqual(event.data.kind, AI_ACTION_ORB_ATTENTION)
        self.assertEqual(event.data.action_id, "screen_done")


if __name__ == "__main__":
    unittest.main()
