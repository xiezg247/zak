"""主窗口快捷键：单源定义，按类别分组。

侧栏页面：Ctrl+1–9（与侧栏顺序一致）
弹窗工具：Ctrl+Shift+…（回测 / 后台 / 笔记）
全局：Ctrl+F / Ctrl+L（及 macOS Meta+L）
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from pydantic import Field
from vnpy.trader.ui import QtGui

from vnpy_common.domain.base import FrozenModel

if TYPE_CHECKING:
    from vnpy_ashare.ui.shell.main_window import AshareMainWindow


class ShortcutEntry(FrozenModel):
    action_key: str = Field(description="动作键")
    label: str = Field(description="展示标签")
    sequence: str = Field(description="Qt 快捷键序列")


class ShortcutGroup(FrozenModel):
    title: str = Field(description="分组标题")
    entries: tuple[ShortcutEntry, ...] = Field(description="快捷键项")


SIDEBAR_SHORTCUT_GROUP = ShortcutGroup(
    title="侧栏页面",
    entries=(
        ShortcutEntry(action_key="home", label="守则", sequence="Ctrl+1"),
        ShortcutEntry(action_key="watchlist", label="自选", sequence="Ctrl+2"),
        ShortcutEntry(action_key="strategy_monitor", label="策略", sequence="Ctrl+3"),
        ShortcutEntry(action_key="market", label="市场", sequence="Ctrl+4"),
        ShortcutEntry(action_key="sector_flow", label="板块资金", sequence="Ctrl+5"),
        ShortcutEntry(action_key="radar", label="雷达", sequence="Ctrl+6"),
        ShortcutEntry(action_key="screener", label="选股", sequence="Ctrl+7"),
        ShortcutEntry(action_key="info_feed", label="信息流", sequence="Ctrl+8"),
        ShortcutEntry(action_key="ai_assistant", label="AI 助手", sequence="Ctrl+9"),
    ),
)

BACKTEST_SHORTCUT_GROUP = ShortcutGroup(
    title="回测（弹窗）",
    entries=(
        ShortcutEntry(action_key="cta_backtest", label="策略回测", sequence="Ctrl+Shift+8"),
        ShortcutEntry(action_key="batch_backtest", label="回测对比", sequence="Ctrl+Shift+9"),
    ),
)

BACKSTAGE_SHORTCUT_GROUP = ShortcutGroup(
    title="后台（弹窗）",
    entries=(
        ShortcutEntry(action_key="scheduler", label="定时任务", sequence="Ctrl+Shift+0"),
        ShortcutEntry(action_key="data_manager", label="数据管理", sequence="Ctrl+Shift+D"),
        ShortcutEntry(action_key="local", label="本地数据", sequence="Ctrl+Shift+L"),
    ),
)

NOTES_SHORTCUT_GROUP = ShortcutGroup(
    title="笔记（弹窗）",
    entries=(ShortcutEntry(action_key="notes_center", label="笔记中心", sequence="Ctrl+Shift+N"),),
)

GLOBAL_SHORTCUT_GROUP = ShortcutGroup(
    title="全局",
    entries=(
        ShortcutEntry(action_key="focus_search", label="聚焦当前页搜索框", sequence="Ctrl+F"),
        ShortcutEntry(action_key="toggle_ai_orb", label="显示/隐藏 AI 悬浮球", sequence="Ctrl+L"),
    ),
)

SHORTCUT_GROUPS: tuple[ShortcutGroup, ...] = (
    SIDEBAR_SHORTCUT_GROUP,
    BACKTEST_SHORTCUT_GROUP,
    BACKSTAGE_SHORTCUT_GROUP,
    NOTES_SHORTCUT_GROUP,
    GLOBAL_SHORTCUT_GROUP,
)


def _entries_to_dict(entries: tuple[ShortcutEntry, ...]) -> dict[str, str]:
    return {entry.action_key: entry.sequence for entry in entries}


NAV_SHORTCUTS: dict[str, str] = _entries_to_dict(SIDEBAR_SHORTCUT_GROUP.entries)
BACKTEST_SHORTCUTS: dict[str, str] = _entries_to_dict(BACKTEST_SHORTCUT_GROUP.entries)
BACKSTAGE_SHORTCUTS: dict[str, str] = _entries_to_dict(BACKSTAGE_SHORTCUT_GROUP.entries)
NOTES_CENTER_SHORTCUT = NOTES_SHORTCUT_GROUP.entries[0].sequence


def format_shortcuts_help() -> str:
    lines: list[str] = []
    for group in SHORTCUT_GROUPS:
        lines.append(group.title)
        for entry in group.entries:
            lines.append(f"  {entry.sequence:14}  {entry.label}")
        lines.append("")
    lines.append("  Meta+L          显示/隐藏 AI 悬浮球（macOS）")
    return "\n".join(lines).rstrip()


def bind_main_window_shortcuts(
    win: AshareMainWindow,
    *,
    show_page: Callable[[int], None],
    focus_quotes_search: Callable[[], None],
    toggle_floating_orb: Callable[[], None],
) -> None:
    from vnpy_ashare.ui.shell.nav import APP_NAV_ENTRIES

    for index, entry in enumerate(APP_NAV_ENTRIES):
        shortcut = NAV_SHORTCUTS.get(entry.key)
        if not shortcut:
            continue
        action = QtGui.QAction(f"打开{entry.label}", win)
        action.setShortcut(QtGui.QKeySequence(shortcut))
        action.triggered.connect(lambda _checked=False, i=index: show_page(i))
        win.addAction(action)

    focus_search = QtGui.QAction("聚焦搜索", win)
    focus_search.setShortcut(QtGui.QKeySequence("Ctrl+F"))
    focus_search.triggered.connect(focus_quotes_search)
    win.addAction(focus_search)

    toggle_orb = QtGui.QAction("显示/隐藏 AI 悬浮球", win)
    toggle_orb.setShortcuts([QtGui.QKeySequence("Ctrl+L"), QtGui.QKeySequence("Meta+L")])
    toggle_orb.triggered.connect(toggle_floating_orb)
    win.addAction(toggle_orb)
