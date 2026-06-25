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
) -> bool:
    """配置单只回测是否在主工具栏展示。"""
    show_backtest = False if policy is not None else page.config.show_backtest_button
    page.backtest_button.setVisible(show_backtest)
    if hasattr(page, "move_watchlist_up_button"):
        page.move_watchlist_up_button.hide()
    if hasattr(page, "move_watchlist_down_button"):
        page.move_watchlist_down_button.hide()
    return show_backtest


def watchlist_toolbar_group3_visible(
    page: WatchlistPoolHost,
    *,
    policy: WatchlistToolbarPolicy | None,
    show_backtest_in_toolbar: bool,
) -> bool:
    return (
        page.config.show_add_watchlist_button
        or page.config.show_remove_watchlist_button
        or (page.config.show_download_button and policy is None)
        or show_backtest_in_toolbar
        or page.config.show_batch_backtest_button
        or page.config.show_fill_button
        or (policy is not None and (page.config.show_watchlist_signals or page.config.show_watchlist_positions))
    )
