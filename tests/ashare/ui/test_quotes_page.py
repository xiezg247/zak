"""行情页 K 线加载竞态校验测试。"""

from __future__ import annotations

import unittest

from vnpy.trader.constant import Exchange

from vnpy_ashare.ui.quotes.controllers.local_data import should_apply_loaded_bars


class LoadedBarsApplyTests(unittest.TestCase):
    def test_apply_when_symbol_and_scope_match(self) -> None:
        key = ("600519", Exchange.SSE)
        self.assertTrue(
            should_apply_loaded_bars(
                generation=2,
                current_generation=2,
                request_id=3,
                current_request_id=3,
                target_key=key,
                current_key=key,
                target_scope="daily",
                current_scope="daily",
                loaded_key=key,
            )
        )

    def test_reject_stale_generation(self) -> None:
        key = ("600519", Exchange.SSE)
        self.assertFalse(
            should_apply_loaded_bars(
                generation=1,
                current_generation=2,
                request_id=3,
                current_request_id=3,
                target_key=key,
                current_key=key,
                target_scope="daily",
                current_scope="daily",
                loaded_key=key,
            )
        )

    def test_reject_stale_request(self) -> None:
        key = ("600519", Exchange.SSE)
        self.assertFalse(
            should_apply_loaded_bars(
                generation=2,
                current_generation=2,
                request_id=2,
                current_request_id=3,
                target_key=key,
                current_key=key,
                target_scope="daily",
                current_scope="daily",
                loaded_key=key,
            )
        )

    def test_reject_symbol_mismatch(self) -> None:
        self.assertFalse(
            should_apply_loaded_bars(
                generation=2,
                current_generation=2,
                request_id=3,
                current_request_id=3,
                target_key=("600519", Exchange.SSE),
                current_key=("000001", Exchange.SZSE),
                target_scope="daily",
                current_scope="daily",
                loaded_key=("600519", Exchange.SSE),
            )
        )

    def test_reject_scope_mismatch(self) -> None:
        key = ("600519", Exchange.SSE)
        self.assertFalse(
            should_apply_loaded_bars(
                generation=2,
                current_generation=2,
                request_id=3,
                current_request_id=3,
                target_key=key,
                current_key=key,
                target_scope="1m",
                current_scope="daily",
                loaded_key=key,
            )
        )

    def test_reject_mismatched_loaded_symbol(self) -> None:
        key = ("600519", Exchange.SSE)
        self.assertFalse(
            should_apply_loaded_bars(
                generation=2,
                current_generation=2,
                request_id=3,
                current_request_id=3,
                target_key=key,
                current_key=key,
                target_scope="daily",
                current_scope="daily",
                loaded_key=("000001", Exchange.SZSE),
            )
        )


if __name__ == "__main__":
    unittest.main()
