"""选股批量操作测试。"""

from __future__ import annotations

from vnpy_ashare.screener.batch.batch_actions import rows_to_stock_items, watchlist_items_to_rows


def test_rows_to_stock_items_deduplicates():
    rows = [
        {"vt_symbol": "600000.SSE", "name": "浦发银行"},
        {"vt_symbol": "600000.SSE", "name": "重复"},
        {"vt_symbol": "000001.SZSE", "name": "平安银行"},
        {"vt_symbol": "invalid", "name": "无效"},
    ]
    items = rows_to_stock_items(rows)
    assert len(items) == 2
    assert items[0].symbol == "600000"
    assert items[1].symbol == "000001"


def test_rows_to_stock_items_accepts_screener_result_row():
    from vnpy_ashare.domain.screener.result_row import ScreenerResultRow

    rows = [
        ScreenerResultRow.from_mapping({"vt_symbol": "600519.SSE", "name": "贵州茅台"}),
    ]
    items = rows_to_stock_items(rows)
    assert len(items) == 1
    assert items[0].symbol == "600519"


def test_watchlist_items_to_rows():
    rows = watchlist_items_to_rows(
        [
            {"symbol": "600519", "exchange": "SSE", "name": "贵州茅台"},
            {"symbol": "", "exchange": "SSE", "name": "无效"},
        ]
    )
    assert rows == [{"vt_symbol": "600519.SSE", "name": "贵州茅台"}]
