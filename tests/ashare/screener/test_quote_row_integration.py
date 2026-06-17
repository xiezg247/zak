"""ScreeningResultContext / ScreenerRunResult ScreenerResultRow 集成测试。"""

from __future__ import annotations

from vnpy_ashare.ai.context.store import get_screening_results, set_screening_results
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.screener.run.result import ScreenerRunResult
from vnpy_ashare.screener.run.run_store import get_run, save_run


def test_screener_run_result_coerces_dict_rows() -> None:
    result = ScreenerRunResult(
        rows=[{"vt_symbol": "600519.SSE", "symbol": "600519", "change_pct": 1.2}],
        condition="测试",
        updated_at="2026-06-17",
        total_scanned=100,
        source="quote",
    )
    assert len(result.rows) == 1
    assert isinstance(result.rows[0], ScreenerResultRow)
    assert result.rows[0].quote.vt_symbol == "600519.SSE"


def test_screener_run_result_splits_recipe_fields() -> None:
    result = ScreenerRunResult(
        rows=[
            {
                "vt_symbol": "600519.SSE",
                "symbol": "600519",
                "composite_score": 88.0,
                "hit_reason": "动量",
            }
        ],
        condition="配方",
        updated_at="2026-06-17",
        total_scanned=100,
        source="recipe",
    )
    row = result.rows[0]
    assert row.scores["composite_score"] == 88.0
    assert row.tags["hit_reason"] == "动量"
    assert row["composite_score"] == 88.0


def test_screening_context_roundtrip() -> None:
    set_screening_results(
        condition="配方A",
        rows=[{"symbol": "000001", "vt_symbol": "000001.SZSE", "change_pct": 2.0}],
        updated_at="2026-06-17",
    )
    ctx = get_screening_results()
    assert ctx is not None
    assert ctx.count == 1
    assert isinstance(ctx.rows[0], ScreenerResultRow)
    assert ctx.rows[0].get("change_pct") == 2.0
    set_screening_results(condition="", rows=[], updated_at=None)


def test_run_store_persists_screener_result_rows() -> None:
    record = save_run(
        condition="落库测试",
        source="quote",
        rows=[{"vt_symbol": "600000.SSE", "symbol": "600000", "name": "浦发银行"}],
        total_scanned=10,
    )
    loaded = get_run(record.id)
    assert loaded is not None
    assert isinstance(loaded.rows[0], ScreenerResultRow)
    assert loaded.rows[0].get("name") == "浦发银行"
