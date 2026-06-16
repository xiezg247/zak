"""自选多维看盘 loader / sort 测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from vnpy_ashare.quotes.watchlist_multiview.loader import build_watchlist_multiview_board
from vnpy_ashare.quotes.watchlist_multiview.models import WatchlistMultiRow
from vnpy_ashare.quotes.watchlist_multiview.sort import sort_multiview_rows
from vnpy_ashare.ui.quotes.watchlist_multiview.settings import (
    load_grid_columns,
    load_sort_key,
    load_view_mode,
    save_grid_columns,
    save_sort_key,
    save_view_mode,
)


def _sample_row(
    *,
    vt_symbol: str = "600000.SSE",
    sort_order: int = 0,
    change_pct: float | None = 1.0,
    anomaly_score: float = 5.0,
    signal_label: str | None = None,
    has_position: bool = False,
    position_pnl_pct: float | None = None,
    industry: str | None = None,
    sector_rank: int | None = None,
    sparkline_points: tuple[float, ...] = (),
) -> WatchlistMultiRow:
    return WatchlistMultiRow(
        vt_symbol=vt_symbol,
        symbol=vt_symbol.split(".")[0],
        name="测试",
        sort_order=sort_order,
        last_price=10.0,
        change_pct=change_pct,
        volume_ratio=1.2,
        turnover_rate=2.0,
        change_speed_5m=0.5,
        metric_label="涨幅",
        metric_value="+1.00%",
        sub_label="量比",
        sub_value="1.20",
        anomaly_score=anomaly_score,
        signal_label=signal_label,
        has_position=has_position,
        position_pnl_pct=position_pnl_pct,
        industry=industry,
        sector_rank=sector_rank,
        sparkline_points=sparkline_points,
        sparkline_kind="daily" if sparkline_points else "none",
    )


class WatchlistMultiViewSortTests(unittest.TestCase):
    def test_sort_by_change_pct_desc(self) -> None:
        rows = [
            _sample_row(vt_symbol="600000.SSE", change_pct=1.0, anomaly_score=1.0),
            _sample_row(vt_symbol="000001.SZSE", change_pct=3.0, anomaly_score=2.0),
        ]
        sorted_rows = sort_multiview_rows(rows, sort_key="change_pct")
        self.assertEqual([row.vt_symbol for row in sorted_rows], ["000001.SZSE", "600000.SSE"])

    def test_sort_by_sort_order(self) -> None:
        rows = [
            _sample_row(vt_symbol="600000.SSE", sort_order=2),
            _sample_row(vt_symbol="000001.SZSE", sort_order=1),
        ]
        sorted_rows = sort_multiview_rows(rows, sort_key="sort_order")
        self.assertEqual([row.vt_symbol for row in sorted_rows], ["000001.SZSE", "600000.SSE"])


class WatchlistMultiViewLoaderTests(unittest.TestCase):
    def test_empty_watchlist(self) -> None:
        with patch(
            "vnpy_ashare.quotes.watchlist_multiview.loader.load_watchlist_rows",
            return_value=[],
        ):
            data = build_watchlist_multiview_board()
        self.assertEqual(data.rows, ())
        self.assertIn("自选池为空", data.empty_message)

    def test_build_rows_for_watchlist(self) -> None:
        watchlist = [("600000", Exchange.SSE, "浦发"), ("000001", Exchange.SZSE, "平安")]
        quotes = {
            "600000.SSE": {
                "vt_symbol": "600000.SSE",
                "symbol": "600000",
                "name": "浦发",
                "last_price": 10.5,
                "change_pct": 2.5,
                "volume_ratio": 1.4,
                "turnover_rate": 1.1,
            },
            "000001.SZSE": {
                "vt_symbol": "000001.SZSE",
                "symbol": "000001",
                "name": "平安",
                "last_price": 12.0,
                "change_pct": -1.0,
                "volume_ratio": 0.9,
                "turnover_rate": 0.8,
            },
        }
        with (
            patch(
                "vnpy_ashare.quotes.watchlist_multiview.loader.load_watchlist_rows",
                return_value=watchlist,
            ),
            patch(
                "vnpy_ashare.quotes.watchlist_multiview.loader._quotes_for_candidates",
                return_value=quotes,
            ),
            patch(
                "vnpy_ashare.quotes.radar.radar_moneyflow.enrich_quotes_with_moneyflow",
                side_effect=lambda payload: payload,
            ),
        ):
            data = build_watchlist_multiview_board(sort_key="change_pct")
        self.assertEqual(len(data.rows), 2)
        self.assertEqual(data.rows[0].vt_symbol, "600000.SSE")
        self.assertEqual(data.rows[0].metric_label, "涨幅")


class WatchlistMultiViewEnrichTests(unittest.TestCase):
    def test_enrich_signal_position_sector(self) -> None:
        from vnpy_ashare.domain.position_snapshot import PositionSnapshot
        from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
        from vnpy_ashare.quotes.market.market_overview_loaders import SectorRankItem
        from vnpy_ashare.quotes.watchlist_multiview.enrich import enrich_multiview_rows

        base = (
            _sample_row(vt_symbol="600000.SSE", industry=None),
            _sample_row(vt_symbol="000001.SZSE", industry=None),
        )
        signal = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="test",
            as_of="2025-01-01",
            signal="buy",
            signal_label="买入",
            signal_date="2025-01-01",
            ref_buy_price=10.0,
            ref_sell_price=None,
            strength=80.0,
            reason_summary="test",
            reasons=(),
            warnings=(),
        )
        position = PositionSnapshot(
            vt_symbol="000001.SZSE",
            name="平安",
            cost_price=10.0,
            volume=100,
            buy_date="2025-01-01",
            source="manual",
            last_price=11.0,
            market_value=1100.0,
            unrealized_pnl=100.0,
            unrealized_pnl_pct=10.0,
            exit_signal="hold",
            signal_snapshot=None,
            t1_locked=False,
            exit_ref_price=None,
            dist_exit_pct=None,
            warnings=(),
        )
        with (
            patch(
                "vnpy_ashare.quotes.watchlist_multiview.enrich.load_sector_ranks",
                return_value=[SectorRankItem(industry="银行", avg_change_pct=1.2, count=10)],
            ),
            patch(
                "vnpy_ashare.quotes.watchlist_multiview.enrich.get_stock_industry_map",
                return_value={"600000.SH": "银行"},
            ),
        ):
            rows = enrich_multiview_rows(
                base,
                signal_symbols={"600000.SSE"},
                signal_cache={"600000.SSE": signal},
                position_cache={"000001.SZSE": position},
                sparklines={"600000.SSE": (10.0, 10.5, 11.0)},
                sparkline_kind="intraday",
            )
        self.assertEqual(rows[0].signal_label, "买入")
        self.assertEqual(rows[0].sector_rank, 1)
        self.assertEqual(rows[0].sparkline_points, (10.0, 10.5, 11.0))
        self.assertEqual(rows[0].sparkline_kind, "intraday")
        self.assertTrue(rows[1].has_position)
        self.assertEqual(rows[1].position_pnl_pct, 10.0)


class WatchlistMultiViewSummaryTests(unittest.TestCase):
    def test_build_board_summary(self) -> None:
        from vnpy_ashare.domain.position_snapshot import PositionSnapshot
        from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
        from vnpy_ashare.quotes.watchlist_multiview.summary import build_multiview_board_summary

        rows = (
            _sample_row(vt_symbol="600000.SSE", change_pct=2.0, anomaly_score=15.0),
            _sample_row(vt_symbol="000001.SZSE", change_pct=-1.0, anomaly_score=3.0),
        )
        signal = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="test",
            as_of="2025-01-01",
            signal="buy",
            signal_label="买入",
            signal_date="2025-01-01",
            ref_buy_price=10.0,
            ref_sell_price=None,
            strength=80.0,
            reason_summary="test",
            reasons=(),
            warnings=(),
        )
        position = PositionSnapshot(
            vt_symbol="000001.SZSE",
            name="平安",
            cost_price=10.0,
            volume=100,
            buy_date="2025-01-01",
            source="manual",
            last_price=11.0,
            market_value=1100.0,
            unrealized_pnl=100.0,
            unrealized_pnl_pct=5.0,
            exit_signal="hold",
            signal_snapshot=None,
            t1_locked=False,
            exit_ref_price=None,
            dist_exit_pct=None,
            warnings=(),
        )
        text = build_multiview_board_summary(
            rows,
            signal_symbols={"600000.SSE"},
            signal_cache={"600000.SSE": signal},
            position_cache={"000001.SZSE": position},
        )
        self.assertIn("自选多维", text)
        self.assertIn("信号区", text)
        self.assertIn("持仓", text)
        self.assertIn("异动前列", text)


class WatchlistMultiViewSparklineDataTests(unittest.TestCase):
    def test_downsample_closes(self) -> None:
        from datetime import datetime

        from vnpy.trader.constant import Exchange, Interval
        from vnpy.trader.object import BarData

        from vnpy_ashare.quotes.watchlist_multiview.sparkline_data import closes_from_bars

        bars = [
            BarData(
                symbol="600000",
                exchange=Exchange.SSE,
                datetime=datetime(2025, 1, 1),
                interval=Interval.DAILY,
                open_price=float(i),
                high_price=float(i),
                low_price=float(i),
                close_price=float(i),
                volume=1.0,
                gateway_name="TEST",
            )
            for i in range(1, 11)
        ]
        points = closes_from_bars(bars, max_points=5)
        self.assertEqual(len(points), 5)
        self.assertEqual(points[0], 1.0)
        self.assertEqual(points[-1], 10.0)


class WatchlistMultiViewSettingsTests(unittest.TestCase):
    def test_view_mode_defaults_table(self) -> None:
        save_view_mode("table")
        self.assertEqual(load_view_mode(), "table")

    def test_view_mode_roundtrip_multiview(self) -> None:
        save_view_mode("multiview")
        self.assertEqual(load_view_mode(), "multiview")
        save_view_mode("table")

    def test_sort_key_roundtrip(self) -> None:
        save_sort_key("anomaly_score")
        self.assertEqual(load_sort_key(), "anomaly_score")
        save_sort_key("sort_order")

    def test_grid_columns_roundtrip(self) -> None:
        save_grid_columns(4)
        self.assertEqual(load_grid_columns(), 4)
        save_grid_columns(3)


if __name__ == "__main__":
    unittest.main()
