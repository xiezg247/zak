"""飞书 interactive 卡片测试。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from vnpy_ashare.notifications.content.delivery import build_notify_outbound, interactive_cards_enabled
from vnpy_ashare.notifications.content.feishu_card import build_feishu_interactive_card, notify_open_url
from vnpy_ashare.notifications.core.events import (
    NOTIFY_EVENT_EMOTION_STAGE_CHANGE,
    NOTIFY_EVENT_MANUAL_TEST,
    NOTIFY_EVENT_RISK_GATE_CHANGE,
)


class FeishuCardTest(unittest.TestCase):
    def test_build_emotion_card(self) -> None:
        card = build_feishu_interactive_card(
            NOTIFY_EVENT_EMOTION_STAGE_CHANGE,
            {
                "stage_label": "启动",
                "limit_up_count": 55,
                "limit_down_count": 3,
                "position_pct_max": 0.5,
            },
        )
        self.assertEqual(card["header"]["title"]["content"], "情绪阶段变更")
        body = card["elements"][0]["text"]["content"]
        self.assertIn("启动", body)

    @patch.dict(os.environ, {"NOTIFY_OPEN_URL": "https://example.com/zak"}, clear=False)
    def test_card_includes_button_when_open_url(self) -> None:
        self.assertEqual(notify_open_url(), "https://example.com/zak")
        card = build_feishu_interactive_card(NOTIFY_EVENT_MANUAL_TEST, {})
        action = card["elements"][-1]
        self.assertEqual(action["tag"], "action")
        self.assertEqual(action["actions"][0]["url"], "https://example.com/zak")

    @patch.dict(os.environ, {"NOTIFY_OPEN_URL": ""}, clear=False)
    def test_card_note_without_open_url(self) -> None:
        card = build_feishu_interactive_card(
            NOTIFY_EVENT_RISK_GATE_CHANGE,
            {"state_label": "警戒", "warnings": [], "daily_pnl_pct": -3.0},
        )
        self.assertEqual(card["elements"][-1]["tag"], "note")

    @patch.dict(os.environ, {"NOTIFY_FEISHU_INTERACTIVE": "false"}, clear=False)
    def test_outbound_text_only_when_disabled(self) -> None:
        self.assertFalse(interactive_cards_enabled())
        outbound = build_notify_outbound(NOTIFY_EVENT_MANUAL_TEST, {})
        self.assertIsNone(outbound.interactive_card)
        self.assertIn("测试", outbound.text)

    @patch.dict(os.environ, {"NOTIFY_FEISHU_INTERACTIVE": "true"}, clear=False)
    def test_outbound_includes_card_when_enabled(self) -> None:
        self.assertTrue(interactive_cards_enabled())
        outbound = build_notify_outbound(NOTIFY_EVENT_MANUAL_TEST, {})
        self.assertIsNotNone(outbound.interactive_card)
