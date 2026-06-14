"""配方结果展示字段补全测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.data.data_source import enrich_recipe_rows


def test_enrich_recipe_rows_fills_cross_dimension_fields() -> None:
    rows = [
        {
            "vt_symbol": "600000.SSE",
            "symbol": "600000",
            "name": "浦发银行",
            "net_mf_amount": 100_000,
            "composite_score": 95.0,
        },
        {
            "vt_symbol": "000001.SZSE",
            "symbol": "000001",
            "name": "平安银行",
            "pe_ttm": 5.5,
            "turnover_rate": 1.2,
            "composite_score": 90.0,
        },
    ]
    fund_rows = [
        {
            "ts_code": "600000.SH",
            "vt_symbol": "600000.SSE",
            "symbol": "600000",
            "name": "浦发银行",
            "close": 10.5,
            "pe_ttm": 6.1,
            "turnover_rate": 0.8,
            "trade_date": "20260612",
        },
        {
            "ts_code": "000001.SZ",
            "vt_symbol": "000001.SZSE",
            "symbol": "000001",
            "name": "平安银行",
            "close": 12.0,
            "pe_ttm": 5.5,
            "turnover_rate": 1.2,
            "trade_date": "20260612",
        },
    ]
    mf_rows = [
        {
            "ts_code": "600000.SH",
            "vt_symbol": "600000.SSE",
            "net_mf_amount": 100_000,
        },
        {
            "ts_code": "000001.SZ",
            "vt_symbol": "000001.SZSE",
            "net_mf_amount": 50_000,
        },
    ]

    with (
        patch(
            "vnpy_ashare.screener.data.data_source.fetch_fundamental_screening_rows",
            return_value=(fund_rows, "20260612", "tushare"),
        ),
        patch(
            "vnpy_ashare.screener.data.data_source.fetch_daily_pct_map",
            return_value={"600000.SH": 2.5, "000001.SZ": -1.1},
        ),
        patch(
            "vnpy_ashare.screener.data.data_source.fetch_moneyflow_with_fallback",
            return_value=(mf_rows, "20260612"),
        ),
    ):
        enriched = enrich_recipe_rows(rows)

    moneyflow_row = next(row for row in enriched if row["vt_symbol"] == "600000.SSE")
    assert moneyflow_row["change_pct"] == 2.5
    assert moneyflow_row["pe_ttm"] == 6.1
    assert moneyflow_row["turnover_rate"] == 0.8
    assert moneyflow_row["net_mf_amount"] == 100_000

    valuation_row = next(row for row in enriched if row["vt_symbol"] == "000001.SZSE")
    assert valuation_row["change_pct"] == -1.1
    assert valuation_row["net_mf_amount"] == 50_000
    assert valuation_row["pe_ttm"] == 5.5
