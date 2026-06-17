"""选股 run diff 测试。"""

from __future__ import annotations

from vnpy_ashare.domain.screener.result_row import coerce_screener_result_row
from vnpy_ashare.screener.run.run_diff import annotate_rows_with_diff, compute_run_diff, enrich_condition_run, enrich_recipe_run


def _row(vt_symbol: str, **fields: object):
    payload = {"vt_symbol": vt_symbol, **fields}
    return coerce_screener_result_row(payload)


def test_compute_run_diff():
    current = [
        _row("600000.SSE", name="A"),
        _row("600001.SSE", name="B"),
    ]
    previous = [
        _row("600000.SSE", name="A"),
        _row("600002.SSE", name="C"),
    ]
    diff = compute_run_diff(current, previous)
    assert diff["new_count"] == 1
    assert diff["stay_count"] == 1
    assert diff["drop_count"] == 1
    assert "600001.SSE" in diff["new"]
    assert "600002.SSE" in diff["drop"]


def test_annotate_rows_with_diff():
    rows = [_row("600000.SSE", name="A")]
    diff = {"new": ["600000.SSE"], "stay": []}
    annotated = annotate_rows_with_diff(rows, diff)
    assert annotated[0].tags["diff_status"] == "新增"


def test_enrich_recipe_run_without_previous():
    from unittest.mock import patch

    config: dict = {}
    rows = [_row("600000.SSE", amount=50_000_000)]
    with patch("vnpy_ashare.screener.run.run_diff.find_previous_run_by_recipe", return_value=None):
        result = enrich_recipe_run(rows, "intraday_multi", config)
    assert len(result) == 1
    assert result[0].get("vt_symbol") == "600000.SSE"
    assert result[0].get("amount") == 50_000_000
    assert "run_diff" not in config


def test_enrich_condition_run_with_previous():
    from unittest.mock import Mock, patch

    previous = Mock()
    previous.id = "prev-1"
    previous.rows = [_row("600000.SSE")]
    config: dict = {}
    rows = [
        _row("600000.SSE", amount=50_000_000),
        _row("600001.SSE", amount=50_000_000),
    ]
    with patch(
        "vnpy_ashare.screener.run.run_diff.find_previous_run_by_condition",
        return_value=previous,
    ):
        result = enrich_condition_run(rows, "雷达共振", config, source="radar")
    assert result[0].tags["diff_status"] == "保留"
    assert result[1].tags["diff_status"] == "新增"
    assert config["run_diff"]["new_count"] == 1
