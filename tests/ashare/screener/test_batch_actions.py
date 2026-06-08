"""选股批量操作测试。"""

from __future__ import annotations

from vnpy_ashare.screener.batch_actions import rows_to_stock_items


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
