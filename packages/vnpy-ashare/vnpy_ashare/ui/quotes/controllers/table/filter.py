"""行情表格筛选（自选 / 本地 / 关键词）。"""

from __future__ import annotations

from vnpy_ashare.domain.data.bar_health import BarHealthStatus
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.ui.quotes.controllers.table.base import TableControllerBase
from vnpy_ashare.ui.quotes.page.config import MAX_DISPLAY_ROWS
from vnpy_ashare.ui.quotes.page.roles import STRATEGY_MONITOR_PAGE
from vnpy_ashare.ui.quotes.watchlist.quote_status import append_loading_suffix


class TableFilterMixin(TableControllerBase):
    def apply_local_page_display(self) -> None:
        """本地页：渲染当前页并更新状态（全库搜索由 load_stock_list 分页加载）。"""
        page = self._p
        page.display_stocks = list(page.all_stocks)
        self.render_table()
        page._pagination.set_visible()
        page._pagination.update_controls()
        keyword = page.search_edit.text().strip()
        if page._local_total == 0 and not keyword:
            label = page._local_scope_label()
            page.status_label.setText(f"暂无本地{label}，请在自选页下载")
        elif page._local_total == 0 and keyword:
            page.status_label.setText(f"未找到匹配「{keyword}」的本地标的")
        else:
            matched = page.display_stocks
            stale = sum(
                1
                for item in matched
                if page.bar_list_status.get(
                    (item.symbol, item.exchange),
                    BarHealthStatus.UNKNOWN,
                )
                in (BarHealthStatus.STALE, BarHealthStatus.GAPS)
            )
            status = page._pagination.format_local_status()
            if stale:
                status += f"，本页 {stale} 只需补全"
            page.status_label.setText(status)
        page._local.update_batch_toolbar_buttons()

    def apply_filter(self) -> None:
        page = self._p
        if not page._active:
            return

        if page.config.use_market_rank:
            if page.market_auto_refresh_enabled():
                page._market_page = 0
                page._market_page_cache.clear()
                page._pagination.set_visible()
                if page.market_uses_client_pagination():
                    self.filter_market_display()
                else:
                    page.load_market_page()
                return
            if page.config.market_full_list:
                page._market_page = 0
                page._pagination.set_visible()
                if page.market_uses_client_pagination():
                    self.filter_market_display()
                else:
                    page._market_page_cache.clear()
                    page.load_market_page()
                return
            page._market_page = 0
            page._market_page_cache.clear()
            page._market_loading_more = False
            page._market_last_load_more_at = 0.0
            page.load_market_page()
            return

        keyword = page.search_edit.text().strip().lower()

        if page.config.use_local_pagination:
            if keyword == page._local_filter_keyword:
                return
            page._local_filter_keyword = keyword
            page._market_page = 0
            page.load_stock_list()
            return

        if page.config.require_keyword and not keyword:
            page.display_stocks = []
            self._model().set_row_count(0)
            page._quote_timer.stop()
            page.status_label.setText(f"共 {len(page.all_stocks)} 只 A 股，请输入关键词搜索（最多 {MAX_DISPLAY_ROWS} 条）")
            return

        matched = [s for s in page.all_stocks if keyword in s.search_key] if keyword else list(page.all_stocks)
        next_display = matched[:MAX_DISPLAY_ROWS]
        display_unchanged = self._same_stock_list(page.display_stocks, next_display)
        page.display_stocks = next_display
        if page.config.show_market_table:
            table_rows = self._model().row_count()
            if not display_unchanged or table_rows != len(next_display) or page.config.use_local_table:
                self.render_table()
        if page.config.auto_refresh_quotes:
            if is_ashare_trading_session():
                page.refresh_quotes()
            page.schedule_quote_auto_refresh()
        else:
            page._quote_timer.stop()

        self.update_display_status(matched=matched)

    def update_display_status(self, *, matched: list | None = None) -> None:
        page = self._p
        if matched is None:
            keyword = page.search_edit.text().strip().lower()
            matched = [s for s in page.all_stocks if keyword in s.search_key] if keyword else list(page.all_stocks)

        extra = f"，显示前 {MAX_DISPLAY_ROWS} 条" if len(matched) > MAX_DISPLAY_ROWS else ""
        groups = getattr(page, "_watchlist_groups", None)
        if not matched and page.config.scope_key == "自选池":
            if page.page_name == STRATEGY_MONITOR_PAGE:
                status = "自选池为空，请在市场页加入自选后再监控"
            elif groups is not None and groups.is_filtering():
                status = f"分组「{groups.active_group_label()}」暂无标的，可在右键菜单中勾选加入"
            else:
                status = "自选池为空，请在市场页搜索标的并点击「加入自选」"
        elif not matched and page.config.use_local_table:
            label = page._local_scope_label()
            status = f"暂无本地{label}，请在自选页下载"
        elif page.config.use_local_table:
            stale = sum(
                1
                for item in matched
                if page.bar_list_status.get(
                    (item.symbol, item.exchange),
                    BarHealthStatus.UNKNOWN,
                )
                in (BarHealthStatus.STALE, BarHealthStatus.GAPS)
            )
            status = f"{page.page_name}  共 {len(matched)} 只{extra}"
            if stale:
                status += f"，{stale} 只需补全"
            page._local.update_batch_toolbar_buttons()
        elif page.page_name == STRATEGY_MONITOR_PAGE:
            status = f"自选池 {len(matched)} 只{extra}"
        else:
            status = f"{page.page_name}  匹配 {len(matched)} 只{extra}"

        page.status_label.setText(append_loading_suffix(page, status))
