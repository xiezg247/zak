"""FeishuWebhookChannel 测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.notifications.channels.feishu_webhook import FeishuWebhookChannel


class FeishuWebhookChannelTest(unittest.TestCase):
    @patch("vnpy_ashare.notifications.channels.feishu_webhook.requests.post")
    def test_send_text_success(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"StatusCode": 0})
        channel = FeishuWebhookChannel("https://open.feishu.cn/open-apis/bot/v2/hook/test")
        result = channel.send_text("【zak】测试")
        self.assertTrue(result.success)
        body = mock_post.call_args.kwargs["json"]
        self.assertEqual(body["msg_type"], "text")
        self.assertEqual(body["content"]["text"], "【zak】测试")

    def test_send_text_empty_url(self) -> None:
        channel = FeishuWebhookChannel("")
        result = channel.send_text("【zak】测试")
        self.assertFalse(result.success)
        self.assertIn("未配置", result.message)

    @patch("vnpy_ashare.notifications.channels.feishu_webhook.requests.post")
    def test_send_interactive_success(self, mock_post: MagicMock) -> None:
        from vnpy_ashare.notifications.models import NotifyOutboundMessage

        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"StatusCode": 0})
        channel = FeishuWebhookChannel("https://open.feishu.cn/open-apis/bot/v2/hook/test")
        card = {"header": {"title": {"tag": "plain_text", "content": "测试"}}, "elements": []}
        result = channel.send_outbound(NotifyOutboundMessage(text="", interactive_card=card))
        self.assertTrue(result.success)
        body = mock_post.call_args.kwargs["json"]
        self.assertEqual(body["msg_type"], "interactive")
        self.assertEqual(body["card"]["header"]["title"]["content"], "测试")

    @patch("vnpy_ashare.notifications.channels.feishu_webhook.requests.post")
    def test_send_text_with_secret_sign(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(status_code=200, json=lambda: {"StatusCode": 0})
        channel = FeishuWebhookChannel(
            "https://open.feishu.cn/open-apis/bot/v2/hook/test",
            webhook_secret="sec123",
        )
        result = channel.send_text("【zak】测试")
        self.assertTrue(result.success)
        body = mock_post.call_args.kwargs["json"]
        self.assertIn("timestamp", body)
        self.assertIn("sign", body)
        self.assertEqual(body["msg_type"], "text")

    @patch("vnpy_ashare.notifications.channels.feishu_webhook.requests.post")
    def test_send_text_status_code_non_zero(self, mock_post: MagicMock) -> None:
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"StatusCode": 9499, "StatusMessage": "bad request"},
        )
        channel = FeishuWebhookChannel("https://open.feishu.cn/open-apis/bot/v2/hook/test")
        result = channel.send_text("【zak】测试")
        self.assertFalse(result.success)
