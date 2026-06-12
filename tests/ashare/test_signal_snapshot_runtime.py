"""信号快照盘中提示与锚点估算（无 UI 依赖）。"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import tests._bootstrap  # noqa: F401

_ROOT = Path(__file__).resolve().parents[2]
_PKG = _ROOT / "packages" / "vnpy-ashare"


def _load_module(name: str, rel_path: str):
    full_name = f"_test_{name}"
    spec = importlib.util.spec_from_file_location(full_name, _PKG / rel_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


_quote_mod = _load_module("quote_snapshot", "vnpy_ashare/quotes/snapshot.py")
sys.modules["vnpy_ashare.quotes.snapshot"] = _quote_mod
_signal_mod = _load_module("signal_snapshot", "vnpy_ashare/domain/signal_snapshot.py")

QuoteSnapshot = _quote_mod.QuoteSnapshot
SignalSnapshot = _signal_mod.SignalSnapshot
build_price_field_explanations = _signal_mod.build_price_field_explanations
build_runtime_signal_hints = _signal_mod.build_runtime_signal_hints
dist_anchor_exceeds_warn = _signal_mod.dist_anchor_exceeds_warn
dist_buy_pct = _signal_mod.dist_buy_pct
resolve_display_anchor_prices = _signal_mod.resolve_display_anchor_prices
resolve_list_ref_prices = _signal_mod.resolve_list_ref_prices
signal_cell_text = _signal_mod.signal_cell_text
format_signal_context_extra = _signal_mod.format_signal_context_extra
build_intraday_cross_hints = _signal_mod.build_intraday_cross_hints
detect_signal_transitions = _signal_mod.detect_signal_transitions
signal_snapshot_to_dict = _signal_mod.signal_snapshot_to_dict
signal_is_fresh = _signal_mod.signal_is_fresh
signal_is_strong = _signal_mod.signal_is_strong


class DistAnchorWarnTests(unittest.TestCase):
    def test_dist_anchor_warn_when_deviation_large(self) -> None:
        self.assertEqual(dist_buy_pct(47.08, 40.79), -13.36)
        self.assertTrue(dist_anchor_exceeds_warn(47.08, 40.79))

    def test_dist_anchor_ok_when_close(self) -> None:
        self.assertFalse(dist_anchor_exceeds_warn(10.0, 10.5))


class RuntimeSignalHintTests(unittest.TestCase):
    def test_runtime_hints_for_sell_with_action_refs(self) -> None:
        snap = SignalSnapshot(
            vt_symbol="002230.SZSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-10",
            signal="sell",
            signal_label="卖出",
            signal_date="2026-06-06",
            ref_buy_price=47.08,
            ref_sell_price=47.97,
            strength=44.0,
            reason_summary="死叉",
            reasons=("MA 死叉",),
            warnings=(),
            last_close=41.20,
            action_ref_buy_price=39.50,
            action_ref_sell_price=41.20,
        )
        quote = QuoteSnapshot(
            symbol="002230",
            name="科大讯飞",
            last_price=40.79,
            prev_close=42.29,
            open_price=41.50,
            high_price=42.00,
            low_price=40.53,
            change_amount=-1.50,
            change_pct=-3.55,
            turnover_rate=2.5,
            volume=510400.0,
            amount=2098000000.0,
            amplitude=3.24,
            trade_time="15:00:00",
        )
        hints = build_runtime_signal_hints(snap, quote=quote, slow_window=20, fast_window=10)
        joined = "\n".join(hints)
        self.assertIn("偏离支撑锚点", joined)
        self.assertIn("跌破慢线", joined)

    def test_list_ref_prices_sell_uses_quote_for_action_sell(self) -> None:
        snap = SignalSnapshot(
            vt_symbol="002230.SZSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-10",
            signal="sell",
            signal_label="卖出",
            signal_date="2026-06-06",
            ref_buy_price=47.08,
            ref_sell_price=47.97,
            strength=44.0,
            reason_summary="死叉",
            reasons=(),
            warnings=(),
            last_close=41.20,
            action_ref_buy_price=39.50,
            action_ref_sell_price=41.20,
        )
        quote = QuoteSnapshot(
            symbol="002230",
            name="科大讯飞",
            last_price=40.79,
            prev_close=42.29,
            open_price=41.50,
            high_price=42.00,
            low_price=40.53,
            change_amount=-1.50,
            change_pct=-3.55,
            turnover_rate=2.5,
            volume=510400.0,
            amount=2098000000.0,
            amplitude=3.24,
            trade_time="15:00:00",
        )
        list_buy, list_sell = resolve_list_ref_prices(
            snap,
            quote=quote,
            slow_window=20,
            fast_window=10,
        )
        self.assertEqual(list_buy, 39.50)
        self.assertEqual(list_sell, 40.79)
        anchor_text, _ = signal_cell_text(
            "anchor_buy",
            snap,
            quote=quote,
            slow_window=20,
            fast_window=10,
        )
        ref_text, _ = signal_cell_text(
            "ref_buy_price",
            snap,
            quote=quote,
            slow_window=20,
            fast_window=10,
        )
        self.assertTrue(anchor_text.startswith("47."))
        self.assertEqual(ref_text, "39.50")

    def test_field_explanations_for_sell(self) -> None:
        lines = build_price_field_explanations("sell", fast_window=10, slow_window=20)
        joined = "\n".join(lines)
        self.assertIn("支撑锚点", joined)
        self.assertIn("阻力锚点", joined)
        self.assertIn("参考买价", joined)
        self.assertIn("参考卖价", joined)

    def test_resolve_display_anchor_prices_adjusts_with_quote(self) -> None:
        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-10",
            signal="hold",
            signal_label="观望",
            signal_date=None,
            ref_buy_price=10.00,
            ref_sell_price=11.00,
            strength=40.0,
            reason_summary="",
            reasons=(),
            warnings=(),
            last_close=10.50,
        )
        quote = QuoteSnapshot(
            symbol="600000",
            name="浦发银行",
            last_price=11.00,
            prev_close=10.50,
            open_price=10.60,
            high_price=11.10,
            low_price=10.55,
            change_amount=0.50,
            change_pct=4.76,
            turnover_rate=1.0,
            volume=10000.0,
        )
        buy, sell, adjusted = resolve_display_anchor_prices(
            snap,
            quote=quote,
            slow_window=20,
            fast_window=10,
        )
        self.assertTrue(adjusted)
        self.assertEqual(buy, 10.03)
        self.assertEqual(sell, 11.05)

    def test_format_signal_context_extra_includes_runtime_hints(self) -> None:
        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-10",
            signal="buy",
            signal_label="买入",
            signal_date="2026-06-08",
            ref_buy_price=10.00,
            ref_sell_price=11.00,
            strength=80.0,
            reason_summary="金叉",
            reasons=("MA 金叉",),
            warnings=(),
            last_close=10.50,
            action_ref_buy_price=10.00,
            action_ref_sell_price=11.00,
        )
        quote = QuoteSnapshot(
            symbol="600000",
            name="浦发银行",
            last_price=10.20,
            prev_close=10.50,
            open_price=10.40,
            high_price=10.60,
            low_price=10.10,
            change_amount=-0.30,
            change_pct=-2.86,
            turnover_rate=1.0,
            volume=10000.0,
        )
        text = format_signal_context_extra(
            snap,
            quote=quote,
            slow_window=20,
            fast_window=10,
        )
        self.assertIn("策略信号：买入", text)
        self.assertIn("参考买价", text)
        self.assertIn("距买价%", text)

    def test_intraday_cross_hints_near_golden_cross(self) -> None:
        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-10",
            signal="hold",
            signal_label="观望",
            signal_date=None,
            ref_buy_price=10.00,
            ref_sell_price=9.98,
            strength=40.0,
            reason_summary="",
            reasons=(),
            warnings=(),
            last_close=10.00,
            fast_ma=9.98,
            slow_ma=10.00,
        )
        quote = QuoteSnapshot(
            symbol="600000",
            name="浦发银行",
            last_price=10.01,
            prev_close=10.00,
            open_price=10.00,
            high_price=10.05,
            low_price=9.98,
            change_amount=0.01,
            change_pct=0.10,
            turnover_rate=1.0,
            volume=10000.0,
        )
        hints = build_intraday_cross_hints(
            snap,
            quote=quote,
            slow_window=20,
            fast_window=10,
        )
        joined = "\n".join(hints)
        self.assertTrue(
            "金叉" in joined or "高于慢线" in joined or "临界交叉" in joined,
            joined,
        )

    def test_intraday_cross_hints_virtual_death_cross_on_buy(self) -> None:
        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-10",
            signal="buy",
            signal_label="买入",
            signal_date="2026-06-08",
            ref_buy_price=10.00,
            ref_sell_price=10.01,
            strength=80.0,
            reason_summary="金叉",
            reasons=(),
            warnings=(),
            last_close=10.01,
            fast_ma=10.01,
            slow_ma=10.00,
        )
        quote = QuoteSnapshot(
            symbol="600000",
            name="浦发银行",
            last_price=9.50,
            prev_close=10.01,
            open_price=10.10,
            high_price=10.10,
            low_price=9.45,
            change_amount=-0.70,
            change_pct=-6.86,
            turnover_rate=1.0,
            volume=10000.0,
        )
        hints = build_intraday_cross_hints(
            snap,
            quote=quote,
            slow_window=20,
            fast_window=10,
        )
        self.assertTrue(any("虚拟死叉" in hint for hint in hints))

    def test_detect_signal_transitions(self) -> None:
        def _snap(signal: str, label: str) -> SignalSnapshot:
            return SignalSnapshot(
                vt_symbol="600000.SSE",
                strategy_id="AshareDoubleMaStrategy",
                as_of="2026-06-10",
                signal=signal,
                signal_label=label,
                signal_date=None,
                ref_buy_price=10.0,
                ref_sell_price=11.0,
                strength=50.0,
                reason_summary="",
                reasons=(),
                warnings=(),
            )

        before = {"600000.SSE": _snap("hold", "观望")}
        after = {"600000.SSE": _snap("buy", "买入")}
        lines = detect_signal_transitions(before, after, name_for=lambda _vt: "浦发银行")
        self.assertEqual(lines, ("浦发银行（600000.SSE）：观望 → 买入",))

    def test_signal_snapshot_to_dict(self) -> None:
        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-10",
            signal="buy",
            signal_label="买入",
            signal_date="2026-06-08",
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=80.0,
            reason_summary="金叉",
            reasons=("MA 金叉",),
            warnings=(),
            fast_ma=11.0,
            slow_ma=10.0,
            volume_ratio_5d=1.35,
            ma_gap_pct=10.0,
            strength_cross=80.0,
            strength_alignment=90.0,
            strength_volume=50.0,
            strength_pattern=30.0,
        )
        payload = signal_snapshot_to_dict(snap)
        self.assertEqual(payload["signal"], "buy")
        self.assertEqual(payload["fast_ma"], 11.0)
        self.assertEqual(payload["volume_ratio_5d"], 1.35)
        self.assertEqual(payload["strength_cross"], 80.0)

    def test_signal_age_and_label_badges(self) -> None:
        format_signal_label_display = _signal_mod.format_signal_label_display
        signal_cell_text = _signal_mod.signal_cell_text
        format_strength_breakdown = _signal_mod.format_strength_breakdown

        snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-10",
            signal="buy",
            signal_label="买入",
            signal_date="2026-06-01",
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=72.0,
            reason_summary="金叉",
            reasons=(),
            warnings=(),
            volume_ratio_5d=1.6,
            ma_gap_pct=2.5,
            strength_cross=80.0,
            strength_alignment=90.0,
            strength_volume=80.0,
            strength_pattern=30.0,
            relative_index_pct=3.5,
        )
        label = format_signal_label_display(snap, bar_end_date="2026-06-09")
        self.assertIn("K旧", label)
        self.assertIn("过期", label)
        self.assertTrue(
            signal_is_fresh(
                _signal_mod.SignalSnapshot(
                    vt_symbol="600000.SSE",
                    strategy_id="AshareDoubleMaStrategy",
                    as_of="2026-06-10",
                    signal="buy",
                    signal_label="买入",
                    signal_date="2026-06-08",
                    ref_buy_price=10.0,
                    ref_sell_price=11.0,
                    strength=72.0,
                    reason_summary="",
                    reasons=(),
                    warnings=(),
                )
            )
        )
        self.assertFalse(signal_is_fresh(snap))
        self.assertTrue(signal_is_strong(snap))
        sell_text, sell_sort = signal_cell_text(
            "dist_sell_pct",
            snap,
            quote=QuoteSnapshot(
                symbol="600000",
                name="浦发银行",
                last_price=11.5,
                prev_close=11.0,
                open_price=11.0,
                high_price=11.6,
                low_price=10.9,
                change_amount=0.5,
                change_pct=4.55,
                turnover_rate=1.0,
                volume=10000.0,
            ),
        )
        self.assertEqual(sell_text, "+4.55")
        broken_snap = SignalSnapshot(
            vt_symbol="600000.SSE",
            strategy_id="AshareDoubleMaStrategy",
            as_of="2026-06-10",
            signal="buy",
            signal_label="买入",
            signal_date="2026-06-08",
            ref_buy_price=10.0,
            ref_sell_price=11.0,
            strength=80.0,
            reason_summary="",
            reasons=(),
            warnings=(),
            last_close=10.0,
        )
        broken_label = format_signal_label_display(
            broken_snap,
            quote=QuoteSnapshot(
                symbol="600000",
                name="浦发银行",
                last_price=9.5,
                prev_close=10.0,
                open_price=10.0,
                high_price=10.1,
                low_price=9.4,
                change_amount=-0.5,
                change_pct=-5.0,
                turnover_rate=1.0,
                volume=10000.0,
            ),
        )
        self.assertIn("破", broken_label)
        age_text, age_sort = signal_cell_text("signal_age", snap)
        self.assertEqual(age_text, "9天")
        self.assertEqual(age_sort, 9)
        ratio_text, ratio_sort = signal_cell_text("volume_ratio", snap)
        self.assertEqual(ratio_text, "1.60")
        self.assertEqual(ratio_sort, 1.6)
        gap_text, gap_sort = signal_cell_text("ma_gap_pct", snap)
        self.assertEqual(gap_text, "+2.50")
        self.assertEqual(gap_sort, 2.5)
        breakdown = format_strength_breakdown(snap)
        self.assertIn("综合强度：72", breakdown)
        self.assertIn("交叉 80", breakdown)
        rel_text, rel_sort = signal_cell_text("relative_index_pct", snap)
        self.assertEqual(rel_text, "+3.50")
        self.assertEqual(rel_sort, 3.5)


class SignalPanelColumnTests(unittest.TestCase):
    def test_normalize_and_resolve_columns(self) -> None:
        columns_mod = _load_module(
            "signal_panel_columns",
            "vnpy_ashare/ui/quotes/watchlist_signals/columns.py",
        )
        keys = columns_mod.normalize_visible_optional_keys(["signal_strength", "signal", "signal", "unknown"])
        self.assertEqual(keys[0], "signal")
        self.assertIn("signal_strength", keys)
        self.assertNotIn("unknown", keys)
        cols = columns_mod.resolve_signal_panel_columns(["signal", "has_position"])
        self.assertEqual(cols[0], ("symbol", "代码"))
        self.assertIn(("has_position", "持仓"), cols)
        self.assertNotIn(("volume_ratio", "量比"), cols)


class SignalBenchmarkTests(unittest.TestCase):
    def test_benchmark_return_from_index_rows(self) -> None:
        benchmark_mod = _load_module(
            "signal_benchmark",
            "vnpy_ashare/domain/signal_benchmark.py",
        )
        rows = [
            {"ts_code": "000300.SH", "trade_date": "20250601", "close": 3800.0},
            {"ts_code": "000300.SH", "trade_date": "20250602", "close": 3810.0},
            {"ts_code": "000001.SH", "trade_date": "20250602", "close": 3000.0},
            {"ts_code": "000300.SH", "trade_date": "20250603", "close": 3900.0},
        ]
        pct = benchmark_mod.benchmark_return_from_index_rows(rows, lookback=20)
        self.assertEqual(pct, round((3900 - 3800) / 3800 * 100, 2))


if __name__ == "__main__":
    unittest.main()
