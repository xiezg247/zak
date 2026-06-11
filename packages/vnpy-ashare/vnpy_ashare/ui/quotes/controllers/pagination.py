"""市场页分页控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.domain.quote_time import format_batch_updated_at
from vnpy_ashare.ui.quotes.workers import MarketPageResult

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


class MarketPaginationController:
    """市场榜分页 UI 与导航。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    def page_count(self) -> int:
        page_size = self._page.config.market_page_size
        if self._page._market_total <= 0 or page_size <= 0:
            return 1
        return max((self._page._market_total + page_size - 1) // page_size, 1)

    def uses_pagination(self) -> bool:
        return self.should_show_pagination()

    def should_show_pagination(self) -> bool:
        page = self._page
        if not page.config.use_market_rank or page.config.market_scroll_paging:
            return False
        if page.market_auto_refresh_enabled():
            return True
        return not page.config.market_full_list

    def set_visible(self, visible: bool | None = None) -> None:
        page = self._page
        if visible is None:
            visible = self.should_show_pagination()
        page.home_button.setVisible(visible)
        page.prev_page_button.setVisible(visible)
        page.next_page_button.setVisible(visible)
        page.end_button.setVisible(visible)
        page.page_label.setVisible(visible)
        page.page_total_label.setVisible(visible)
        page.page_jump_input.setVisible(visible)

    def update_controls(self) -> None:
        if not self.uses_pagination():
            return
        page_count = self.page_count()
        current = min(self._page._market_page + 1, page_count)
        if not self._page.page_jump_input.hasFocus():
            self._page.page_jump_input.setText(str(current))
        self._page.page_total_label.setText(f"/ {page_count} 页")
        self._page.home_button.setEnabled(self._page._market_page > 0)
        self._page.prev_page_button.setEnabled(self._page._market_page > 0)
        self._page.next_page_button.setEnabled(self._page._market_page + 1 < page_count)
        self._page.end_button.setEnabled(self._page._market_page + 1 < page_count)

    def update_busy_state(self, busy: bool) -> None:
        if not self.uses_pagination():
            return
        page_count = self.page_count()
        self._page.home_button.setEnabled(not busy and self._page._market_page > 0)
        self._page.prev_page_button.setEnabled(not busy and self._page._market_page > 0)
        self._page.next_page_button.setEnabled(not busy and self._page._market_page + 1 < page_count)
        self._page.end_button.setEnabled(not busy and self._page._market_page + 1 < page_count)
        self._page.page_jump_input.setEnabled(not busy)

    def _apply_page_view(self) -> None:
        self._page.apply_market_page_view()

    def go_prev(self) -> None:
        if self._page._market_page <= 0:
            return
        self._page._market_page -= 1
        self._apply_page_view()

    def go_next(self) -> None:
        if self._page._market_page + 1 >= self.page_count():
            return
        self._page._market_page += 1
        self._apply_page_view()

    def go_home(self) -> None:
        if self._page._market_page <= 0:
            return
        self._page._market_page = 0
        self._apply_page_view()

    def go_end(self) -> None:
        page_count = self.page_count()
        if self._page._market_page + 1 >= page_count:
            return
        self._page._market_page = max(page_count - 1, 0)
        self._apply_page_view()

    def jump(self) -> None:
        try:
            target = int(self._page.page_jump_input.text())
            page_count = self.page_count()
            if 1 <= target <= page_count:
                self._page._market_page = target - 1
                self._apply_page_view()
        except ValueError:
            self._page.page_jump_input.setText(str(self._page._market_page + 1))

    def on_board_changed(self) -> None:
        board = self._page.board_combo.currentText()
        self._page._market_board = board if board != "全部" else None
        self._page._market_board_base = None
        self._page._market_board_base_key = None
        self._page._market_filter_keyword = ""
        self._page._market_page = 0
        if self._page.market_uses_client_pagination():
            self._page._table.filter_market_display()
            return
        if self._page.config.market_full_list and not self._page.market_auto_refresh_enabled():
            if self._page._market_catalog_loaded:
                self._page._table.filter_market_display()
            else:
                self._page.load_market_full()
            return
        self._page._market_page_cache.clear()
        self._page._market_loading_more = False
        self._page._market_last_load_more_at = 0.0
        self._page.load_market_page()

    def format_status(self, result: MarketPageResult) -> str:
        page_count = max(
            (result.total + result.page_size - 1) // result.page_size,
            1,
        )
        current = min(result.page + 1, page_count)
        if result.mode == "search":
            status = f"搜索匹配 {result.total} 只，第 {current}/{page_count} 页"
        elif result.mode == "rank":
            status = f"{self._page.active_rank_title()} {result.total} 只，第 {current}/{page_count} 页"
        else:
            status = f"共 {result.total} 只，第 {current}/{page_count} 页"
        batch_time = format_batch_updated_at(result.updated_at)
        if batch_time:
            status += f"，行情更新于 {batch_time}"
        elif result.total == 0:
            status += "（Redis 暂无行情，请运行 quote_collector）"
        return status

    def format_scroll_status(
        self,
        *,
        total: int,
        loaded: int,
        updated_at: str | None,
        mode: str,
        loading_more: bool = False,
    ) -> str:
        if mode == "search":
            status = f"搜索匹配 {total} 只，已加载 {loaded}"
        elif mode == "rank":
            status = f"{self._page.active_rank_title()} {total} 只，已加载 {loaded}"
        else:
            status = f"共 {total} 只，已加载 {loaded}"
        if loading_more:
            status += "，加载更多…"
        elif loaded < total:
            status += "，下拉加载更多"
        batch_time = format_batch_updated_at(updated_at)
        if batch_time:
            status += f"，行情更新于 {batch_time}"
        elif total == 0:
            status += "（Redis 暂无行情，请运行 quote_collector）"
        return status
