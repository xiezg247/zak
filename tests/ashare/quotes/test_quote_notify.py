"""Redis 行情 Pub/Sub 通知测试。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.quotes.core import quote_notify as notify


class QuoteNotifyTests(unittest.TestCase):
    def test_publish_skipped_when_disabled(self) -> None:
        prev = os.environ.pop("ZAK_QUOTE_REDIS_NOTIFY", None)
        try:
            client = MagicMock()
            notify.publish_quote_updated(seq=3, client=client)
            client.publish.assert_not_called()
        finally:
            if prev is not None:
                os.environ["ZAK_QUOTE_REDIS_NOTIFY"] = prev

    def test_publish_when_enabled(self) -> None:
        prev = os.environ.get("ZAK_QUOTE_REDIS_NOTIFY")
        os.environ["ZAK_QUOTE_REDIS_NOTIFY"] = "1"
        try:
            client = MagicMock()
            notify.publish_quote_updated(seq=5, client=client)
            client.publish.assert_called_once_with(notify.QUOTE_NOTIFY_CHANNEL, "5")
        finally:
            if prev is None:
                os.environ.pop("ZAK_QUOTE_REDIS_NOTIFY", None)
            else:
                os.environ["ZAK_QUOTE_REDIS_NOTIFY"] = prev


class CollectChainEnrichTests(unittest.TestCase):
    @patch("vnpy_ashare.jobs.runners.warm_market_summary")
    @patch("vnpy_ashare.jobs.runners.enrich_market_quotes")
    @patch("vnpy_ashare.jobs.runners.collect_market_quotes")
    @patch("vnpy_ashare.jobs.runners.collect_defer_enrich_enabled", return_value=True)
    @patch("vnpy_ashare.jobs.runners.is_ashare_trading_session", return_value=True)
    def test_collect_chains_enrich_when_defer(
        self,
        _session: MagicMock,
        _defer: MagicMock,
        collect: MagicMock,
        enrich: MagicMock,
        warm: MagicMock,
    ) -> None:
        from vnpy_ashare.jobs.core.result import JobResult
        from vnpy_ashare.jobs.runners import run_collect_quotes

        collect.return_value = JobResult(success=True, message="写入 100 条")
        enrich.return_value = JobResult(success=True, message="已 enrich 100 条")
        warm.return_value = JobResult(success=True, message="")

        result = run_collect_quotes(force=True)
        enrich.assert_called_once()
        self.assertIn("enrich", result.message)


if __name__ == "__main__":
    unittest.main()
