"""市场页分页控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.quote_time import format_batch_updated_at
from vnpy_ashare.ui.quotes.workers import MarketPageResult

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes_page import QuotesPage


class MarketPaginationController:
    """市场榜分页 UI 与导航。"""

    def __init__(self, page: QuotesPage) -> None:
        self._page = page

    def page_count(self) -> int:
        page_size = self._page.config.market_page_size
        if self._page._market_total <= 0 or page_size <= 0:
            return 1
        return max((self._page._market_total + page_size - 1) // page_size, 1)

    def set_visible(self, visible: bool) -> None:
        page = self._page
        page.home_button.setVisible(visible)
        page.prev_page_button.setVisible(visible)
        page.next_page_button.setVisible(visible)
        page.end_button.setVisible(visible)
        page.page_label.setVisible(visible)
        page.page_total_label.setVisible(visible)
        page.page_jump_input.setVisible(visible)

    def update_controls(self) -> None:
        if not self._page.config.use_market_rank:
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
        if not self._page.config.use_market_rank:
            return
        page_count = self.page_count()
        self._page.home_button.setEnabled(not busy and self._page._market_page > 0)
        self._page.prev_page_button.setEnabled(not busy and self._page._market_page > 0)
        self._page.next_page_button.setEnabled(
            not busy and self._page._market_page + 1 < page_count
        )
        self._page.end_button.setEnabled(
            not busy and self._page._market_page + 1 < page_count
        )
        self._page.page_jump_input.setEnabled(not busy)

    def go_prev(self) -> None:
        if self._page._market_page <= 0:
            return
        self._page._market_page -= 1
        self._page.load_market_page()

    def go_next(self) -> None:
        if self._page._market_page + 1 >= self.page_count():
            return
        self._page._market_page += 1
        self._page.load_market_page()

    def go_home(self) -> None:
        if self._page._market_page <= 0:
            return
        self._page._market_page = 0
        self._page.load_market_page()

    def go_end(self) -> None:
        page_count = self.page_count()
        if self._page._market_page + 1 >= page_count:
            return
        self._page._market_page = max(page_count - 1, 0)
        self._page.load_market_page()

    def jump(self) -> None:
        try:
            target = int(self._page.page_jump_input.text())
            page_count = self.page_count()
            if 1 <= target <= page_count:
                self._page._market_page = target - 1
                self._page.load_market_page()
        except ValueError:
            self._page.page_jump_input.setText(str(self._page._market_page + 1))

    def on_board_changed(self) -> None:
        board = self._page.board_combo.currentText()
        self._page._market_board = board if board != "全部" else None
        self._page._market_page = 0
        self._page.load_market_page()

    def format_status(self, result: MarketPageResult) -> str:
        page_count = max(
            (result.total + result.page_size - 1) // result.page_size,
            1,
        )
        current = min(result.page + 1, page_count)
        if result.mode == "search":
            status = f"搜索匹配 {result.total} 只，第 {current}/{page_count} 页"
        else:
            status = f"共 {result.total} 只，第 {current}/{page_count} 页"
        batch_time = format_batch_updated_at(result.updated_at)
        if batch_time:
            status += f"，行情更新于 {batch_time}"
        elif result.total == 0:
            status += "（Redis 暂无行情，请运行 quote_collector）"
        return status
