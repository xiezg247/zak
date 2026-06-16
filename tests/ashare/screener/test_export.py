"""选股结果列解析测试。"""

from __future__ import annotations

from vnpy_ashare.screener.run.export import resolve_export_columns


def test_resolve_export_columns_quote_only():
    rows = [{"symbol": "A", "last_price": 10, "change_pct": 1, "turnover_rate": 2, "source": "quote"}]
    columns = resolve_export_columns(rows)
    assert columns[3] == ("last_price", "现价")


def test_resolve_export_columns_fundamental_when_data_present():
    rows = [
        {
            "symbol": "A",
            "close": 10,
            "pe_ttm": 12,
            "turnover_rate": 2,
            "source": "tushare",
        }
    ]
    columns = resolve_export_columns(rows)
    assert columns[3] == ("close", "收盘价")


def test_resolve_export_columns_quote_when_tushare_source_without_fundamentals():
    rows = [{"symbol": "A", "turnover_rate": 12.7, "source": "tushare"}]
    columns = resolve_export_columns(rows)
    assert columns[3] == ("last_price", "现价")


def test_resolve_export_columns_moneyflow_primary():
    rows = [{"symbol": "A", "net_mf_amount": 1000, "moneyflow_source": "tushare", "flow_kind": "main"}]
    columns = resolve_export_columns(rows)
    assert columns[3] == ("net_mf_amount", "主力净流入(万)")


def test_resolve_export_columns_quote_enriched_with_net_mf():
    rows = [{"symbol": "A", "last_price": 10, "net_mf_amount": -204, "turnover_rate": 12.7, "source": "quote"}]
    columns = resolve_export_columns(rows)
    assert columns[3] == ("last_price", "现价")
