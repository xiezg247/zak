"""选股 run diff 测试。"""

from __future__ import annotations

from vnpy_ashare.screener.run_diff import annotate_rows_with_diff, compute_run_diff, enrich_recipe_run


def test_compute_run_diff():
    current = [
        {"vt_symbol": "600000.SSE", "name": "A"},
        {"vt_symbol": "600001.SSE", "name": "B"},
    ]
    previous = [
        {"vt_symbol": "600000.SSE", "name": "A"},
        {"vt_symbol": "600002.SSE", "name": "C"},
    ]
    diff = compute_run_diff(current, previous)
    assert diff["new_count"] == 1
    assert diff["stay_count"] == 1
    assert diff["drop_count"] == 1
    assert "600001.SSE" in diff["new"]
    assert "600002.SSE" in diff["drop"]


def test_annotate_rows_with_diff():
    rows = [{"vt_symbol": "600000.SSE", "name": "A"}]
    diff = {"new": ["600000.SSE"], "stay": []}
    annotated = annotate_rows_with_diff(rows, diff)
    assert annotated[0]["diff_status"] == "新增"


def test_enrich_recipe_run_without_previous():
    from unittest.mock import patch

    config: dict = {}
    rows = [{"vt_symbol": "600000.SSE", "amount": 50_000_000}]
    with patch("vnpy_ashare.screener.run_store.find_previous_run_by_recipe", return_value=None):
        result = enrich_recipe_run(rows, "intraday_multi", config)
    assert result == rows
    assert "run_diff" not in config
