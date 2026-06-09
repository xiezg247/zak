"""形态规则单元测试。"""

from __future__ import annotations

import unittest

from vnpy_ashare.screener.pattern_rules import (
    BarSeries,
    match_ma_bull,
    match_old_duck,
    match_w_bottom,
)


def _rising_closes(count: int, *, start: float = 100.0, step: float = 0.8) -> BarSeries:
    closes = [start + index * step for index in range(count)]
    return BarSeries(
        closes=closes,
        highs=[value + 1 for value in closes],
        lows=[value - 1 for value in closes],
        volumes=[1000.0 + index * 10 for index in range(count)],
    )


class PatternRulesTests(unittest.TestCase):
    def test_match_ma_bull_on_uptrend(self) -> None:
        series = _rising_closes(80)
        match = match_ma_bull(series)
        self.assertIsNotNone(match)
        assert match is not None
        self.assertGreater(match.score, 0)
        self.assertIn("MA5", match.hint)

    def test_match_ma_bull_rejects_flat(self) -> None:
        flat = BarSeries(
            closes=[10.0] * 80,
            highs=[10.5] * 80,
            lows=[9.5] * 80,
            volumes=[1000.0] * 80,
        )
        self.assertIsNone(match_ma_bull(flat))

    def test_match_w_bottom_requires_structure(self) -> None:
        series = _rising_closes(80, step=0.1)
        self.assertIsNone(match_w_bottom(series))

    def test_match_old_duck_requires_cross(self) -> None:
        series = _rising_closes(80)
        self.assertIsNone(match_old_duck(series))


if __name__ == "__main__":
    unittest.main()
