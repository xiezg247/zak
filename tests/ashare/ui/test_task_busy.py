"""task_busy：后台任务期间缩小 UI 锁定范围。"""

from __future__ import annotations

from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401


def _page(*, use_market_rank: bool = False, use_local_table: bool = True) -> MagicMock:
    page = MagicMock()
    page.config.use_market_rank = use_market_rank
    page.config.market_full_list = False
    page.config.use_local_table = use_local_table
    page.config.show_board_filter = False
    page.config.show_refresh_quotes_button = False
    page.config.show_sync_button = False
    page.config.show_download_button = True
    page.config.show_fill_button = True
    page.config.show_redownload_button = False
    page.config.show_delete_button = False
    page.config.show_batch_fill_button = False
    page.config.show_batch_gap_fill_button = False
    page.config.show_add_watchlist_button = False
    page.config.show_remove_watchlist_button = False
    page.config.show_watchlist_move_buttons = False
    page.industry_filter = None
    return page


def test_set_busy_with_lock_table_false_keeps_table_enabled() -> None:
    from vnpy_ashare.ui.quotes.page.task_busy import set_busy

    page = _page()
    set_busy(page, True, lock_table=False, lock_search=False)
    page.market_table.setEnabled.assert_not_called()


def test_set_busy_with_lock_search_false_keeps_search_enabled() -> None:
    from vnpy_ashare.ui.quotes.page.task_busy import set_busy

    page = _page()
    set_busy(page, True, lock_table=False, lock_search=False)
    page.search_edit.setEnabled.assert_not_called()
    page.fill_button.setEnabled.assert_called_with(False)


def test_collect_busy_widgets_respects_lock_flags() -> None:
    from vnpy_ashare.ui.quotes.page.task_busy import collect_busy_widgets

    page = _page()
    widgets = collect_busy_widgets(page, lock_table=False, lock_search=False)
    assert page.search_edit not in widgets
    assert page.download_button in widgets
