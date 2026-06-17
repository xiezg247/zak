"""ScreeningResultContext / ScreenerRunResult QuoteRow 集成测试。"""

from __future__ import annotations

from vnpy_ashare.ai.context.store import get_screening_results, set_screening_results
from vnpy_ashare.domain.market.quote_row import QuoteRow
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
    assert isinstance(result.rows[0], QuoteRow)
    assert result.rows[0].vt_symbol == "600519.SSE"


def test_screening_context_roundtrip() -> None:
    set_screening_results(
        condition="配方A",
        rows=[QuoteRow(symbol="000001", vt_symbol="000001.SZSE", change_pct=2.0)],
        updated_at="2026-06-17",
    )
    ctx = get_screening_results()
    assert ctx is not None
    assert ctx.count == 1
    assert isinstance(ctx.rows[0], QuoteRow)
    assert ctx.rows[0].get("change_pct") == 2.0
    set_screening_results(condition="", rows=[], updated_at=None)


def test_run_store_persists_quote_rows() -> None:
    record = save_run(
        condition="落库测试",
        source="quote",
        rows=[{"vt_symbol": "600000.SSE", "symbol": "600000", "name": "浦发银行"}],
        total_scanned=10,
    )
    loaded = get_run(record.id)
    assert loaded is not None
    assert isinstance(loaded.rows[0], QuoteRow)
    assert loaded.rows[0].name == "浦发银行"
