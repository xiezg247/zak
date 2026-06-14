"""笔记 AI 整理 / 扩写辅助函数测试。"""

from __future__ import annotations

import unittest

import tests._bootstrap  # noqa: F401
from vnpy_ashare.ui.quotes.stock_notes.ai_assist import (
    apply_expanded_memo,
    build_journal_polish_messages,
    build_memo_expand_messages,
)


class NoteAiAssistTests(unittest.TestCase):
    def test_build_journal_polish_messages_includes_quote(self) -> None:
        messages = build_journal_polish_messages(
            "放量突破",
            vt_symbol="600519.SSE",
            name="贵州茅台",
            quote_line="现价 1800.00，涨跌 +1.20%",
        )
        self.assertEqual(len(messages), 2)
        user = messages[1]["content"]
        self.assertIn("贵州茅台", user)
        self.assertIn("600519.SSE", user)
        self.assertIn("放量突破", user)
        self.assertIn("1800.00", user)

    def test_build_memo_expand_messages_selection_scope(self) -> None:
        messages = build_memo_expand_messages(
            "全文备忘",
            "选中段",
            vt_symbol="000001.SZSE",
            name="平安银行",
        )
        system = messages[0]["content"]
        self.assertIn("选中段落", system)
        user = messages[1]["content"]
        self.assertIn("全文备忘", user)
        self.assertIn("选中段", user)

    def test_build_memo_expand_messages_empty_raises(self) -> None:
        with self.assertRaises(ValueError):
            build_memo_expand_messages("", "", vt_symbol="000001.SZSE", name="")

    def test_apply_expanded_memo_replaces_selection(self) -> None:
        full = "前文选中后文"
        result = apply_expanded_memo(full, "选中", "扩写内容")
        self.assertEqual(result, "前文扩写内容后文")

    def test_apply_expanded_memo_full_body(self) -> None:
        self.assertEqual(apply_expanded_memo("旧备忘", "", "新备忘"), "新备忘")

    def test_format_quote_snapshot_line(self) -> None:
        from vnpy_ashare.quotes import QuoteSnapshot
        from vnpy_ashare.ui.quotes.stock_notes.ai_assist import format_quote_snapshot_line

        quote = QuoteSnapshot(
            symbol="600519",
            name="贵州茅台",
            last_price=1800.0,
            prev_close=1790.0,
            open_price=1795.0,
            high_price=1810.0,
            low_price=1790.0,
            change_amount=10.0,
            change_pct=1.25,
            turnover_rate=0.5,
            volume=1000.0,
        )
        line = format_quote_snapshot_line(quote)
        self.assertIn("1800.00", line)
        self.assertIn("+1.25%", line)
        self.assertEqual(
            format_quote_snapshot_line(
                QuoteSnapshot(
                    symbol="x",
                    name="",
                    last_price=0,
                    prev_close=0,
                    open_price=0,
                    high_price=0,
                    low_price=0,
                    change_amount=0,
                    change_pct=0,
                    turnover_rate=0,
                    volume=0,
                )
            ),
            "",
        )


if __name__ == "__main__":
    unittest.main()
