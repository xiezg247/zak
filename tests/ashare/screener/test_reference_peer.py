"""参考选股（找同类）单元测试。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.screener.reference_peer import (
    clamp_reference_peer_top_n,
    env_default_reference_peer_top_n,
    run_reference_peer_screen,
)


def test_clamp_reference_peer_top_n():
    assert clamp_reference_peer_top_n(None) == 20
    assert clamp_reference_peer_top_n(0) == 1
    assert clamp_reference_peer_top_n(150) == 100
    assert clamp_reference_peer_top_n(30) == 30


@patch.dict("os.environ", {"REFERENCE_PEER_TOP_N": "35"}, clear=False)
@patch("dotenv.load_dotenv")
def test_env_default_reference_peer_top_n(_mock_load):
    assert env_default_reference_peer_top_n() == 35


def _fund_row(
    symbol: str,
    *,
    ts_code: str,
    pe_ttm: float,
    circ_mv: float,
    name: str = "",
) -> dict:
    return {
        "symbol": symbol,
        "name": name or symbol,
        "vt_symbol": f"{symbol}.SSE",
        "ts_code": ts_code,
        "pe_ttm": pe_ttm,
        "circ_mv": circ_mv,
    }


@patch("vnpy_ashare.screener.reference_peer.fetch_daily_pct_map")
@patch("vnpy_ashare.screener.reference_peer.iter_trade_date_strs")
@patch("vnpy_ashare.screener.reference_peer.fetch_stock_industry_map")
@patch("vnpy_ashare.screener.reference_peer.fetch_daily_basic_with_fallback")
def test_run_reference_peer_screen_ranks_same_industry(
    mock_basic,
    mock_industry,
    mock_dates,
    mock_pct,
):
    mock_basic.return_value = (
        [
            _fund_row("REF", ts_code="600000.SH", pe_ttm=20, circ_mv=1_000_000, name="标杆"),
            _fund_row("A", ts_code="600001.SH", pe_ttm=21, circ_mv=1_050_000, name="甲"),
            _fund_row("B", ts_code="600002.SH", pe_ttm=40, circ_mv=3_000_000, name="乙"),
            _fund_row("C", ts_code="600003.SH", pe_ttm=19, circ_mv=900_000, name="丙"),
            _fund_row("X", ts_code="000001.SZ", pe_ttm=20, circ_mv=1_000_000, name="异业"),
        ],
        "20250606",
    )
    mock_industry.return_value = {
        "600000.SH": "银行",
        "600001.SH": "银行",
        "600002.SH": "银行",
        "600003.SH": "银行",
        "000001.SZ": "保险",
    }
    mock_dates.return_value = ["20250606", "20250605", "20250604", "20250603", "20250602"]
    mock_pct.side_effect = [
        {"600000.SH": 1.0, "600001.SH": 1.2, "600002.SH": -2.0, "600003.SH": 0.8},
        {"600000.SH": 0.5, "600001.SH": 0.4, "600002.SH": 0.0, "600003.SH": 0.6},
        {"600000.SH": -0.2, "600001.SH": -0.1, "600002.SH": 0.3, "600003.SH": -0.3},
        {"600000.SH": 0.0, "600001.SH": 0.0, "600002.SH": 0.0, "600003.SH": 0.0},
        {"600000.SH": 0.0, "600001.SH": 0.0, "600002.SH": 0.0, "600003.SH": 0.0},
    ]

    result = run_reference_peer_screen("REF.SSE", reference_name="标杆", top_n=2)

    assert result.reference_industry == "银行"
    assert len(result.rows) == 2
    symbols = [row["symbol"] for row in result.rows]
    assert "X" not in symbols
    assert symbols[0] in {"A", "C"}
    assert all(row.get("hit_reason") for row in result.rows)
    assert any("同业" in row["hit_reason"] for row in result.rows)


@patch("vnpy_ashare.screener.reference_peer.fetch_stock_industry_map")
@patch("vnpy_ashare.screener.reference_peer.fetch_daily_basic_with_fallback")
def test_run_reference_peer_screen_requires_industry(mock_basic, mock_industry):
    mock_basic.return_value = (
        [_fund_row("REF", ts_code="600000.SH", pe_ttm=20, circ_mv=1_000_000)],
        "20250606",
    )
    mock_industry.return_value = {}

    try:
        run_reference_peer_screen("REF.SSE")
        raised = False
    except RuntimeError as ex:
        raised = True
        assert "行业" in str(ex)

    assert raised
