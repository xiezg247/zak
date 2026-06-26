"""行情页自动刷新调度与提示文案。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from vnpy_ashare.domain.symbols.stock import StockItem
from vnpy_ashare.domain.time.market_hours import CHINA_TZ, is_ashare_trading_session, next_quotes_collect_at
from vnpy_ashare.quotes.core.provider import is_gateway_quote_active
from vnpy_ashare.ui.quotes.page.config import (
    quote_refresh_hint,
    quote_refresh_seconds,
    quote_source_label,
    radar_refresh_hint,
    save_market_auto_refresh_pref,
)
from vnpy_ashare.ui.quotes.page.roles import is_strategy_monitor_page

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def quote_refresh_stock_items(page: QuotesPage) -> list[StockItem]:
    """策略监控页仅拉信号区∪持仓标的；其余页沿用主表展示范围。"""
    if is_strategy_monitor_page(page.page_name):
        from vnpy_ashare.services.focus_pool import load_focus_pool_stock_items

        return load_focus_pool_stock_items()
    if page.config.use_market_rank and page.config.market_full_list and page._market_catalog_loaded and market_auto_refresh_enabled(page):
        return list(page._market_catalog)
    if page.config.market_scroll_paging:
        return page._table.visible_market_items()
    return list(page.display_stocks)


def market_auto_refresh_enabled(page: QuotesPage) -> bool:
    if page.config.use_radar_cards:
        return False
    if page.config.use_market_rank:
        return page._market_auto_refresh
    return page.config.auto_refresh_quotes


def quote_auto_refresh_enabled(page: QuotesPage) -> bool:
    if not page.config.quote_source:
        return False
    return market_auto_refresh_enabled(page)


def quote_auto_refresh_paused_for_hours(page: QuotesPage) -> bool:
    return quote_auto_refresh_enabled(page) and not is_ashare_trading_session()


def schedule_quote_auto_refresh(page: QuotesPage) -> None:
    """按交易时段调度下一次自动刷新（非交易时段休眠至下一段开盘）。"""
    if not page._active or not quote_auto_refresh_enabled(page):
        page._quote_timer.stop()
        update_refresh_hint_label(page)
        return

    now = datetime.now(CHINA_TZ)
    interval_sec = quote_refresh_seconds(page.config.quote_refresh_ms)
    next_at = next_quotes_collect_at(now, interval_seconds=interval_sec)
    delay_ms = max(int((next_at - now).total_seconds() * 1000), 1)
    page._quote_timer.setInterval(delay_ms)
    page._quote_timer.start()
    update_refresh_hint_label(page)


def on_market_auto_refresh_toggled(page: QuotesPage, checked: bool) -> None:
    if page.config.use_radar_cards:
        return
    page._market_auto_refresh = checked
    save_market_auto_refresh_pref(checked)
    update_refresh_hint_label(page)
    page._market_page = 0
    page._market_page_cache.clear()
    page._pagination.set_visible()
    if checked:
        page._market_catalog_loaded = False
        page._market_full_load_quiet = True
        page.load_market_page()
        if is_ashare_trading_session():
            page.refresh_quotes()
        schedule_quote_auto_refresh(page)
    else:
        page._quote_timer.stop()
        if page._market_catalog_loaded:
            page._table.apply_market_display()
        else:
            page._market_full_load_quiet = True
            page.load_market_page()


def update_refresh_hint_label(page: QuotesPage) -> None:
    label = getattr(page, "refresh_hint_label", None)
    if label is None:
        return
    if page.config.use_radar_cards:
        label.setText(radar_refresh_hint())
        return
    auto_refresh = quote_auto_refresh_enabled(page)
    label.setText(
        quote_refresh_hint(
            auto_refresh=auto_refresh,
            refresh_ms=page.config.quote_refresh_ms,
            quote_source=page.config.quote_source,
            paused_for_hours=quote_auto_refresh_paused_for_hours(page),
        )
    )


def update_quote_source_label(page: QuotesPage) -> None:
    label = getattr(page, "quote_source_label", None)
    if label is None:
        return
    text = quote_source_label(
        page.config,
        stream_active=page._stream.use_stream(),
        gateway_active=is_gateway_quote_active(),
    )
    label.setText(text)
    label.setVisible(bool(text))
