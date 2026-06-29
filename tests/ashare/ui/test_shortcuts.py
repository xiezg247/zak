"""快捷键单源定义与分组。"""

from __future__ import annotations

import tests._bootstrap  # noqa: F401


def test_sidebar_shortcuts_match_nav_order() -> None:
    from vnpy_ashare.ui.shell.nav import APP_NAV_ENTRIES
    from vnpy_ashare.ui.shell.shortcuts import NAV_SHORTCUTS, SIDEBAR_SHORTCUT_GROUP

    assert len(SIDEBAR_SHORTCUT_GROUP.entries) == len(APP_NAV_ENTRIES)
    for entry, nav_entry in zip(SIDEBAR_SHORTCUT_GROUP.entries, APP_NAV_ENTRIES, strict=True):
        assert entry.action_key == nav_entry.key
        assert NAV_SHORTCUTS[nav_entry.key] == entry.sequence


def test_reorganized_shortcut_assignments() -> None:
    from vnpy_ashare.ui.shell.shortcuts import BACKSTAGE_SHORTCUTS, BACKTEST_SHORTCUTS, NAV_SHORTCUTS

    assert NAV_SHORTCUTS["strategy_monitor"] == "Ctrl+3"
    assert NAV_SHORTCUTS["market"] == "Ctrl+4"
    assert NAV_SHORTCUTS["radar"] == "Ctrl+6"
    assert NAV_SHORTCUTS["screener"] == "Ctrl+7"
    assert NAV_SHORTCUTS["info_feed"] == "Ctrl+8"
    assert NAV_SHORTCUTS["ai_assistant"] == "Ctrl+9"
    assert BACKTEST_SHORTCUTS["cta_backtest"] == "Ctrl+Shift+8"
    assert BACKTEST_SHORTCUTS["batch_backtest"] == "Ctrl+Shift+9"
    assert BACKSTAGE_SHORTCUTS["scheduler"] == "Ctrl+Shift+0"
    assert BACKSTAGE_SHORTCUTS["data_manager"] == "Ctrl+Shift+D"


def test_format_shortcuts_help_includes_groups() -> None:
    from vnpy_ashare.ui.shell.shortcuts import format_shortcuts_help

    text = format_shortcuts_help()
    assert "侧栏页面" in text
    assert "回测（弹窗）" in text
    assert "后台（弹窗）" in text
    assert "Ctrl+Shift+D" in text
