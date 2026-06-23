"""fear_greed_provider 单元测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from vnpy_ashare.domain.sentiment.fear_greed import FearGreedSnapshot
from vnpy_ashare.screener.sentiment.fear_greed_provider import try_fetch_fear_greed_index
from vnpy_ashare.services import sentiment as sentiment_module


class FearGreedProviderTests(unittest.TestCase):
    def setUp(self) -> None:
        sentiment_module._bound_sentiment = None
        sentiment_module._standalone_sentiment = None

    def test_returns_none_when_compute_fails(self) -> None:
        with patch(
            "vnpy_ashare.screener.sentiment.fear_greed_provider.try_compute_fear_greed",
            return_value=None,
        ):
            self.assertIsNone(try_fetch_fear_greed_index())

    def test_bind_uses_engine_service(self) -> None:
        snapshot = FearGreedSnapshot(
            index=55.0,
            label="中性",
            trade_date="2025-06-23",
            as_of="2025-06-23 15:00:00",
            components=[],
            warnings=[],
            sources=["tushare"],
            disclaimer="",
        )
        svc = MagicMock()
        svc.compute_fear_greed.return_value = snapshot
        sentiment_module.bind_sentiment_service(svc)

        result = try_fetch_fear_greed_index(trade_date="20250623")
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.index, 55.0)
        svc.compute_fear_greed.assert_called_once_with(
            trade_date="20250623",
            include_components=False,
        )


if __name__ == "__main__":
    unittest.main()
