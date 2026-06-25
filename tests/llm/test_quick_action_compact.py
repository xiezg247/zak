"""快捷动作 chip 紧凑展示测试。"""

from __future__ import annotations

import unittest

from vnpy_common.ai.protocol import QuickAction
from vnpy_llm.ui.floating.widgets import compact_quick_actions_for_display


class TestQuickActionCompact(unittest.TestCase):
    def test_assistant_shows_all(self) -> None:
        actions = [QuickAction(id=f"a{i}", label=f"A{i}", prompt="p") for i in range(8)]
        display = compact_quick_actions_for_display(actions, layout_mode="assistant")
        self.assertEqual(len(display), 8)

    def test_floating_overflow_into_more(self) -> None:
        actions = [QuickAction(id=f"a{i}", label=f"A{i}", prompt="p") for i in range(7)]
        display = compact_quick_actions_for_display(actions, layout_mode="floating")
        self.assertEqual(len(display), 5)
        self.assertEqual(display[-1].id, "more_actions")
        self.assertEqual(len(display[-1].children), 3)

    def test_overflow_flattens_submenu(self) -> None:
        actions = [
            QuickAction(id="a", label="A", prompt="a"),
            QuickAction(id="b", label="B", prompt="b"),
            QuickAction(id="c", label="C", prompt="c"),
            QuickAction(
                id="menu",
                label="菜单",
                children=[
                    QuickAction(id="x", label="子1", prompt="x"),
                    QuickAction(id="y", label="子2", prompt="y"),
                ],
            ),
            QuickAction(id="tail", label="尾", prompt="t"),
        ]
        display = compact_quick_actions_for_display(actions, layout_mode="compact", max_primary=4)
        more = display[-1]
        self.assertEqual(more.id, "more_actions")
        self.assertEqual([c.label for c in more.children], ["菜单·子1", "菜单·子2", "尾"])


if __name__ == "__main__":
    unittest.main()
