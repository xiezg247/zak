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
resolve_list_ref_prices = _signal_mod.resolve_list_ref_prices
signal_cell_text = _signal_mod.signal_cell_text


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
        anchor_text, _ = signal_cell_text("anchor_buy", snap, quote=quote)
        ref_text, _ = signal_cell_text(
            "ref_buy_price",
            snap,
            quote=quote,
            slow_window=20,
            fast_window=10,
        )
        self.assertEqual(anchor_text, "47.08")
        self.assertEqual(ref_text, "39.50")

    def test_field_explanations_for_sell(self) -> None:
        lines = build_price_field_explanations("sell", fast_window=10, slow_window=20)
        joined = "\n".join(lines)
        self.assertIn("支撑锚点", joined)
        self.assertIn("阻力锚点", joined)
        self.assertIn("参考买价", joined)
        self.assertIn("参考卖价", joined)


if __name__ == "__main__":
    unittest.main()
