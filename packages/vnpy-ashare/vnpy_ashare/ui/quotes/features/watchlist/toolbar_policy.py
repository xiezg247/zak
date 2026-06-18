"""自选页工具栏 policy（轻量，供 shell / 单测导入）。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.ui.quotes.watchlist.pool_host import WatchlistPoolHost


@dataclass(frozen=True)
class WatchlistToolbarPolicy:
    """自选 feature 页：部分动作移入「更多」或右键，主栏保持精简。"""


def watchlist_toolbar_policy(page: WatchlistPoolHost) -> WatchlistToolbarPolicy | None:
    if getattr(page, "_watchlist_feature", None) is None:
        return None
    return WatchlistToolbarPolicy()


def configure_watchlist_action_button_visibility(
    page: WatchlistPoolHost,
    policy: WatchlistToolbarPolicy | None,
) -> tuple[bool, bool]:
    """配置上移/下移、单只回测可见性。返回 (show_move_in_toolbar, show_backtest_in_toolbar)。"""
    if policy is not None:
        show_move = False
        show_backtest = False
    else:
        show_move = page.config.show_watchlist_move_buttons
        show_backtest = page.config.show_backtest_button
    page.move_watchlist_up_button.setVisible(show_move)
    page.move_watchlist_down_button.setVisible(show_move)
    page.backtest_button.setVisible(show_backtest)
    return show_move, show_backtest


def watchlist_toolbar_group3_visible(
    page: WatchlistPoolHost,
    *,
    policy: WatchlistToolbarPolicy | None,
    show_backtest_in_toolbar: bool,
    show_move_in_toolbar: bool,
) -> bool:
    return (
        page.config.show_add_watchlist_button
        or (page.config.show_download_button and policy is None)
        or show_backtest_in_toolbar
        or page.config.show_batch_backtest_button
        or page.config.show_fill_button
        or show_move_in_toolbar
    )
