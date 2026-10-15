"""市场页 Redis 空时回退 Tushare 收盘快照。"""

from __future__ import annotations

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.time.quote_time import format_market_data_freshness
from vnpy_ashare.quotes.rank.rank_catalog import get_rank_definition
from vnpy_ashare.quotes.rank.rank_scope import load_market_rank_catalog_from_eod


def test_format_market_data_freshness_eod() -> None:
    text = format_market_data_freshness("2026-10-14", source="tushare")
    assert "实时不可用" in text
    assert "收盘" in text


def test_format_market_data_freshness_live() -> None:
    text = format_market_data_freshness("2026-10-15 10:30:00", source="quote")
    assert "行情更新于" in text
    assert "实时不可用" not in text


def test_load_market_rank_catalog_from_eod(monkeypatch) -> None:
    quotes = {
        "600519.SH": QuoteSnapshot(
            symbol="600519.SH",
            name="贵州茅台",
            last_price=1800.0,
            prev_close=1780.0,
            open_price=1785.0,
            high_price=1810.0,
            low_price=1775.0,
            change_amount=20.0,
            change_pct=1.12,
            turnover_rate=0.5,
            volume=1000.0,
            amount=1e8,
        ),
        "000001.SZ": QuoteSnapshot(
            symbol="000001.SZ",
            name="平安银行",
            last_price=10.0,
            prev_close=11.0,
            open_price=10.5,
            high_price=11.0,
            low_price=9.8,
            change_amount=-1.0,
            change_pct=-9.09,
            turnover_rate=1.0,
            volume=2000.0,
            amount=2e7,
        ),
    }
    monkeypatch.setattr(
        "vnpy_ashare.quotes.rank.rank_scope.quotes_from_eod_snapshot",
        lambda: (quotes, "2026-10-14"),
    )
    monkeypatch.setattr(
        "vnpy_ashare.quotes.rank.rank_scope.load_universe_rows",
        lambda: [
            ("600519", __import__("vnpy.trader.constant", fromlist=["Exchange"]).Exchange.SSE, "贵州茅台"),
            ("000001", __import__("vnpy.trader.constant", fromlist=["Exchange"]).Exchange.SZSE, "平安银行"),
        ],
    )
    spec = get_rank_definition("change_pct")
    symbols, ranked_quotes, updated_at = load_market_rank_catalog_from_eod(spec)
    assert updated_at == "2026-10-14"
    assert symbols[0] == "600519.SH"
    assert symbols[-1] == "000001.SZ"
    assert ranked_quotes["600519.SH"].change_pct > 0
