"""飞书群自定义机器人 Webhook。"""

from __future__ import annotations

import logging
import time
from typing import Any

import requests

from vnpy_ashare.notifications.models import NotifyDeliveryResult

logger = logging.getLogger(__name__)

_RETRY_DELAYS_SEC = (1.0, 3.0)
_REQUEST_TIMEOUT_SEC = 10.0


class FeishuWebhookChannel:
    def __init__(self, webhook_url: str) -> None:
        self._webhook_url = webhook_url.strip()

    @property
    def configured(self) -> bool:
        return bool(self._webhook_url)

    def send_text(self, text: str) -> NotifyDeliveryResult:
        if not self._webhook_url:
            return NotifyDeliveryResult(success=False, message="未配置 FEISHU_WEBHOOK_URL")

        payload: dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": text},
        }
        last_error = "发送失败"
        last_status: int | None = None

        for attempt, delay in enumerate((0.0, *_RETRY_DELAYS_SEC)):
            if delay > 0:
                time.sleep(delay)
            try:
                response = requests.post(
                    self._webhook_url,
                    json=payload,
                    timeout=_REQUEST_TIMEOUT_SEC,
                )
                last_status = response.status_code
                if response.status_code != 200:
                    last_error = f"HTTP {response.status_code}"
                    continue
                body = response.json()
                status_code = body.get("StatusCode", body.get("code"))
                if status_code in (0, "0", None):
                    logger.info("feishu notify sent http=%s", response.status_code)
                    return NotifyDeliveryResult(
                        success=True,
                        message="已发送",
                        status_code=response.status_code,
                    )
                last_error = str(body.get("StatusMessage") or body.get("msg") or "StatusCode 非 0")
            except requests.RequestException as ex:
                last_error = str(ex)
                logger.warning("feishu notify attempt=%s failed: %s", attempt + 1, ex)

        logger.warning("feishu notify failed after retries: %s", last_error)
        return NotifyDeliveryResult(
            success=False,
            message=last_error,
            status_code=last_status,
        )
