"""策略元数据 registry 测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from strategies.registry import (
    STRATEGY_REGISTRY,
    format_strategy_guide,
    get_strategy_meta,
)


class StrategyRegistryTests(unittest.TestCase):
    def test_double_ma_registered(self) -> None:
        meta = get_strategy_meta("AshareDoubleMaStrategy")
        self.assertIsNotNone(meta)
        assert meta is not None
        self.assertEqual(meta.class_name, "AshareDoubleMaStrategy")
        self.assertIn("双均线", meta.title)

    def test_unknown_strategy(self) -> None:
        self.assertIsNone(get_strategy_meta("UnknownStrategy"))

    def test_format_guide_contains_sections(self) -> None:
        meta = STRATEGY_REGISTRY["AshareDoubleMaStrategy"]
        html = format_strategy_guide(meta)
        self.assertIn("适用", html)
        self.assertIn("不适用", html)
        self.assertIn("fast_window", html)
        self.assertIn("Ashare", html)


if __name__ == "__main__":
    unittest.main()
