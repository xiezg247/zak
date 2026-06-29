"""并发优化路径单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401


def test_fetch_intraday_moneyflow_map_parallel() -> None:
    from vnpy_ashare.integrations.mcp import intraday_flow

    rows = [{"vt_symbol": f"60000{i}.SSE"} for i in range(3)]
    calls: list[str] = []

    def _fake_query(_tool: str, vt_symbol: str, _symbol: str) -> float:
        calls.append(vt_symbol)
        return float(len(vt_symbol))

    with (
        patch.object(intraday_flow, "mcp_intraday_flow_enabled", return_value=True),
        patch.object(intraday_flow, "_pick_flow_tool", return_value="mcp_tdx_moneyflow"),
        patch.object(intraday_flow, "_query_symbol_flow", side_effect=_fake_query),
        patch.object(intraday_flow, "run_parallel_map", wraps=intraday_flow.run_parallel_map) as parallel,
    ):
        result = intraday_flow.fetch_intraday_moneyflow_map(rows, top_n=3)

    assert parallel.called
    assert len(result) == 3
    assert set(calls) == {row["vt_symbol"] for row in rows}


def test_build_hot_concept_vt_symbol_map_parallel() -> None:
    from vnpy_ashare.integrations.tushare import concept_board

    concept_map = {"885001.TI": "概念A", "885002.TI": "概念B"}
    pct_map = {"885001.TI": 5.0, "885002.TI": 3.0}

    with (
        patch.object(concept_board, "fetch_ths_concept_index_map", return_value=concept_map),
        patch.object(concept_board, "fetch_ths_daily_pct_map", return_value=pct_map),
        patch.object(
            concept_board,
            "fetch_ths_member_vt_symbols",
            side_effect=lambda code: [f"stock_{code}.SSE"],
        ),
        patch.object(concept_board, "run_parallel_map", wraps=concept_board.run_parallel_map) as parallel,
    ):
        vt_map, hot_names = concept_board.build_hot_concept_vt_symbol_map(top_concepts=2)

    assert parallel.called
    assert len(hot_names) == 2
    assert len(vt_map) == 2


def test_load_radar_cards_batch_parallel_buckets() -> None:
    from vnpy_ashare.quotes.radar.loaders import load as radar_load

    items = [
        ("leader_pick", {}),
        ("outlook_watch", {}),
        ("market_emotion", {}),
    ]
    future_results = {
        "full": ({"leader_pick": MagicMock()}, {}),
        "quote": ({"outlook_watch": MagicMock()}, {}),
        "none": ({"market_emotion": MagicMock()}, {}),
    }

    def _fake_load(_batch, *, context_mode, variants):
        return future_results[context_mode]

    futures: list[MagicMock] = []

    def _submit(fn, batch_items, *, context_mode, variants):
        future = MagicMock()
        future.result.side_effect = lambda: fn(batch_items, context_mode=context_mode, variants=variants)
        futures.append(future)
        return future

    with (
        patch.object(radar_load, "_load_radar_cards_in_context", side_effect=_fake_load),
        patch.object(radar_load, "get_io_executor") as get_pool,
        patch.object(radar_load, "as_completed", side_effect=lambda future_map: list(future_map)),
    ):
        mock_pool = MagicMock()
        get_pool.return_value = mock_pool
        mock_pool.submit.side_effect = _submit

        loaded, errors = radar_load.load_radar_cards_batch(items)

    assert get_pool.called
    assert mock_pool.submit.call_count == 3
    assert errors == {}
    assert set(loaded) == {"leader_pick", "outlook_watch", "market_emotion"}


def test_sync_sector_flow_daily_job_parallel() -> None:
    from vnpy_ashare.jobs.prefetch import sector_flow

    with (
        patch.object(sector_flow, "get_tushare_pro", return_value=object()),
        patch.object(sector_flow, "iter_trade_date_strs", return_value=["20240927", "20240926"]),
        patch.object(sector_flow, "_sync_sector_flow_day", side_effect=lambda d: f"{d}:行业1"),
        patch.object(sector_flow, "run_parallel_map", wraps=sector_flow.run_parallel_map) as parallel,
    ):
        result = sector_flow.sync_sector_flow_daily_job()

    assert parallel.called
    assert result.success
    assert "20240927" in result.message
