"""雷达龙头选股单元测试。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from vnpy_ashare.quotes.market.emotion_cycle import classify_emotion_cycle
from vnpy_ashare.quotes.market.emotion_cycle_inputs import EmotionCycleInputs
from vnpy_ashare.quotes.radar.radar_leader import rank_sector_leaders
from vnpy_ashare.screener.run.radar_leader_screen import leader_scored_to_row, run_leader_screen


def _candidate(symbol: str, *, limit_times: int = 3) -> dict:
    return {
        "vt_symbol": f"{symbol}.SSE",
        "symbol": symbol,
        "name": symbol,
        "industry": "半导体",
        "change_pct": 10.0,
        "amount": 3e8,
        "limit_times": limit_times,
        "net_mf_amount": 2e7,
        "last_price": 12.0,
    }


def test_leader_scored_to_row_includes_hit_reason():
    scored = rank_sector_leaders([_candidate("AAA"), _candidate("BBB", limit_times=2)])[0]
    row = leader_scored_to_row(scored)
    assert row["symbol"] == scored.row.symbol
    assert row["source"] == "radar_leader"
    assert "龙头" in row["hit_reason"]
    assert row["leader_tier"] == "dragon_1"


@patch("vnpy_ashare.screener.run.radar_leader_screen.load_emotion_cycle_snapshot")
def test_run_leader_screen_blocks_recession(mock_cycle):
    mock_cycle.return_value = classify_emotion_cycle(
        EmotionCycleInputs(
            limit_up_count=10,
            limit_down_count=25,
            up_ratio=0.2,
            total_amount=2e12,
            max_limit_times=1,
            limit_ladder_depth=0,
        ),
    )
    result = run_leader_screen(top_n=5)
    assert result.rows == []
    assert result.source == "radar_leader"
    assert "不宜新开" in result.condition


@patch("vnpy_ashare.screener.run.radar_leader_screen.enrich_regulatory_tags", side_effect=lambda rows: rows)
@patch("vnpy_ashare.screener.run.radar_leader_screen.attach_first_time_fields")
@patch("vnpy_ashare.screener.run.radar_leader_screen.apply_recipe_filters", side_effect=lambda rows: rows)
@patch("vnpy_ashare.screener.run.radar_leader_screen.build_leader_candidate_pool")
@patch("vnpy_ashare.screener.run.radar_leader_screen.load_emotion_cycle_snapshot", return_value=None)
def test_run_leader_screen_returns_ranked_rows(mock_cycle, mock_pool, _filters, mock_attach, _enrich):
    mock_pool.return_value = ([_candidate("AAA"), _candidate("BBB", limit_times=2)], 5000)
    result = run_leader_screen(top_n=1, variant="mainline")
    assert result.source == "radar_leader"
    assert len(result.rows) == 1
    assert result.rows[0]["symbol"] == "AAA"
    assert result.total_scanned == 5000
    assert "主线龙头" in result.condition
    mock_attach.assert_called_once()


@patch("vnpy_ashare.screener.run.radar_leader_screen.load_emotion_cycle_snapshot", return_value=None)
@patch("vnpy_ashare.screener.run.radar_leader_screen.build_leader_candidate_pool", return_value=([], 0))
def test_run_leader_screen_requires_quotes(_pool, _cycle):
    with pytest.raises(RuntimeError, match="暂无全市场行情"):
        run_leader_screen()


@patch("vnpy_ashare.screener.run.radar_leader_screen.enrich_regulatory_tags", side_effect=lambda rows: rows)
@patch("vnpy_ashare.screener.run.radar_leader_screen.attach_first_time_fields")
@patch("vnpy_ashare.screener.run.radar_leader_screen.rank_leader_pool", return_value=[])
@patch("vnpy_ashare.screener.run.radar_leader_screen.apply_recipe_filters", side_effect=lambda rows: rows)
@patch("vnpy_ashare.screener.run.radar_leader_screen.build_leader_candidate_pool")
@patch("vnpy_ashare.screener.run.radar_leader_screen.load_emotion_cycle_snapshot")
def test_run_leader_screen_divergence_filters_followers(mock_cycle, mock_pool, _filters, mock_rank, _attach, _enrich):
    mock_cycle.return_value = MagicMock(stage="divergence", stage_label="分歧")
    mock_pool.return_value = ([_candidate("A")], 4000)
    run_leader_screen(top_n=10, variant="mainline")
    assert mock_rank.call_args.kwargs.get("filter_followers") is True
