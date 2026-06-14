"""行业成分选股单元测试。"""

from __future__ import annotations

import pytest

from vnpy_ashare.screener.run.industry_screen import run_industry_screen


def _quote(symbol: str, **kwargs) -> dict:
    base = {
        "symbol": symbol,
        "name": symbol,
        "vt_symbol": f"{symbol}.SSE",
        "last_price": 10.0,
        "change_pct": 0.0,
        "turnover_rate": 1.0,
        "volume": 1000,
        "amount": 50_000_000,
    }
    base.update(kwargs)
    return base


def test_run_industry_screen_filters_and_sorts(monkeypatch):
    monkeypatch.setattr(
        "vnpy_ashare.screener.run.industry_screen.attach_industry",
        lambda rows: [{**row, "industry": "银行" if row["symbol"] != "X" else "白酒"} for row in rows],
    )
    rows = run_industry_screen(
        "银行",
        quote_rows=[
            _quote("A", change_pct=2),
            _quote("B", change_pct=5),
            _quote("X", change_pct=9),
        ],
        top_n=2,
    )
    assert rows.condition == "银行 成分"
    assert rows.source == "industry"
    assert [item["symbol"] for item in rows.rows] == ["B", "A"]
    assert rows.total_scanned == 2


def test_run_industry_screen_requires_label():
    with pytest.raises(ValueError, match="行业名称"):
        run_industry_screen("  ")


def test_run_industry_screen_no_constituents(monkeypatch):
    monkeypatch.setattr(
        "vnpy_ashare.screener.run.industry_screen.attach_industry",
        lambda rows: [{**row, "industry": "白酒"} for row in rows],
    )
    with pytest.raises(RuntimeError, match="未找到行业"):
        run_industry_screen("银行", quote_rows=[_quote("A", change_pct=1)])


def test_build_industry_scheme_config():
    from vnpy_ashare.screener.run.runner import build_industry_scheme_config

    config = build_industry_scheme_config("  银行  ", top_n=30)
    assert config == {"kind": "industry", "industry": "银行", "top_n": 30}


def test_run_screener_industry_scheme(monkeypatch):
    from vnpy_ashare.screener.preset.scheme_store import SavedScheme
    from vnpy_ashare.screener.run.runner import ScreenerRequest, run_screener

    scheme = SavedScheme(
        id="s1",
        name="银行成分",
        config={"kind": "industry", "industry": "银行", "top_n": 2},
        created_at="",
        updated_at="",
    )
    monkeypatch.setattr("vnpy_ashare.screener.run.runner.get_scheme", lambda _sid: scheme)
    monkeypatch.setattr(
        "vnpy_ashare.screener.run.industry_screen.attach_industry",
        lambda rows: [{**row, "industry": "银行"} for row in rows],
    )
    result = run_screener(ScreenerRequest(preset="", top_n=20, scheme_id="s1"))
    assert result.condition == "我的方案 · 银行成分"
    assert len(result.rows) <= 2
