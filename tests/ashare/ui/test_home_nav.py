"""主窗口导航结构测试。"""

from __future__ import annotations

from vnpy_ashare.ui.shell.nav import (
    APP_NAV_ENTRIES,
    APP_NAV_GROUPS,
    BACKSTAGE_ENTRIES,
    BACKSTAGE_SHORTCUTS,
    NAV_SHORTCUTS,
)


def test_home_is_first_nav_entry() -> None:
    assert APP_NAV_ENTRIES[0].key == "home"
    assert APP_NAV_ENTRIES[0].label == "守则"


def test_local_in_backstage_not_sidebar() -> None:
    sidebar_keys = {entry.key for group in APP_NAV_GROUPS for entry in group.entries}
    backstage_keys = {entry.key for entry in BACKSTAGE_ENTRIES}
    assert "local" not in sidebar_keys
    assert "local" in backstage_keys
    assert BACKSTAGE_ENTRIES[-1].label == "本地数据"


def test_nav_shortcuts_renumbered() -> None:
    assert NAV_SHORTCUTS["home"] == "Ctrl+1"
    assert NAV_SHORTCUTS["watchlist"] == "Ctrl+2"
    assert "local" not in NAV_SHORTCUTS
    assert BACKSTAGE_SHORTCUTS["local"] == "Ctrl+Shift+L"
