"""SentimentService 单元测试。"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from vnpy_ashare.services.sentiment_service import SentimentService, label_for_index


def test_label_for_index():
    assert label_for_index(10) == "极度恐惧"
    assert label_for_index(50) == "中性"
    assert label_for_index(80) == "极度贪婪"


def test_compute_fear_greed_with_mock_pro():
    engine = SimpleNamespace(main_engine=SimpleNamespace(), event_engine=SimpleNamespace())
    service = SentimentService(engine=engine)

    daily = pd.DataFrame(
        {
            "ts_code": ["000001.SZ", "000002.SZ", "600000.SH", "600519.SH"],
            "pct_chg": [2.0, -1.0, 0.0, 3.5],
        }
    )
    limits = pd.DataFrame({"ts_code": ["A", "B", "C"], "limit": ["U", "U", "D"]})
    index_daily = pd.DataFrame(
        {
            "trade_date": [f"2025060{i}" for i in range(1, 8)],
            "close": [100 + i for i in range(7)],
            "pct_chg": [0.5] * 7,
            "amount": [1000 + i * 10 for i in range(7)],
        }
    )
    north = pd.DataFrame({"trade_date": ["20250609"], "north_money": [120.0]})

    class FakePro:
        def daily(self, **kwargs):
            return daily

        def limit_list_d(self, **kwargs):
            return limits

        def index_daily(self, **kwargs):
            return index_daily

        def moneyflow_hsgt(self, **kwargs):
            return north

    with patch("vnpy_ashare.domain.calendar.last_trading_day", return_value=date(2025, 6, 9)):
        with patch(
            "vnpy_ashare.screener.data.tushare_client.get_tushare_pro",
            return_value=FakePro(),
        ):
            snapshot = service.compute_fear_greed(trade_date="20250609")

    assert 0 <= snapshot.index <= 100
    assert snapshot.label
    assert len(snapshot.components) >= 4
    payload = snapshot.to_dict()
    assert payload["index"] == snapshot.index
