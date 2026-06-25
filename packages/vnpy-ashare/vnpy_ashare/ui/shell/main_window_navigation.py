"""主窗口深链导航（选股 / 板块 / 市场 / 雷达 / 自选）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.trader.ui import QtCore
from vnpy.trader.constant import Exchange

from vnpy_ashare.ui.shell.main_window_pages import nav_index_for_key, show_page_by_key

if TYPE_CHECKING:
    from vnpy_ashare.ui.shell.main_window import AshareMainWindow


def navigate_to_page(win: AshareMainWindow, key: str) -> None:
    nav_index = nav_index_for_key(win, key)
    if nav_index is not None:
        win._show_page(nav_index)
        return
    show_page_by_key(win, key)


def open_screener_run(win: AshareMainWindow, run_id: str, *, page_key: str) -> None:
    if not run_id or page_key not in {"screener", "auto_screener"}:
        return
    nav_index = nav_index_for_key(win, "screener")
    show_page_by_key(win, "screener", nav_index=nav_index)
    widget = win._page_widgets.get("screener")
    if widget is not None and hasattr(widget, "show_historical_run"):
        widget.show_historical_run(run_id, page_key=page_key)


def open_screener_industry(win: AshareMainWindow, industry: str) -> None:
    label = str(industry or "").strip()
    if not label:
        return
    nav_index = nav_index_for_key(win, "screener")
    if nav_index is None:
        return
    show_page_by_key(win, "screener", nav_index=nav_index)
    widget = win._page_widgets.get("screener")
    if widget is not None and hasattr(widget, "run_industry_screen"):
        widget.run_industry_screen(label)


def open_screener_radar_resonance(win: AshareMainWindow) -> None:
    nav_index = nav_index_for_key(win, "screener")
    if nav_index is None:
        return
    show_page_by_key(win, "screener", nav_index=nav_index)
    widget = win._page_widgets.get("screener")
    if widget is not None and hasattr(widget, "run_radar_resonance_screen"):
        widget.run_radar_resonance_screen()


def open_screener_leader_screen(win: AshareMainWindow, *, variant: str = "mainline") -> None:
    nav_index = nav_index_for_key(win, "screener")
    if nav_index is None:
        return
    show_page_by_key(win, "screener", nav_index=nav_index)
    widget = win._page_widgets.get("screener")
    if widget is not None and hasattr(widget, "run_leader_screen"):
        widget.run_leader_screen(variant=variant)


def open_sector_flow(
    win: AshareMainWindow,
    sector_ids: list[str] | None = None,
    *,
    tab: str = "default",
    sector_kind: str | None = None,
) -> None:
    nav_index = nav_index_for_key(win, "sector_flow")
    if nav_index is None:
        return
    show_page_by_key(win, "sector_flow", nav_index=nav_index)
    widget = win._page_widgets.get("sector_flow")
    if widget is None or not hasattr(widget, "focus_sectors"):
        return
    if tab != "default" or sector_ids or sector_kind:
        widget.focus_sectors(
            list(sector_ids or []),
            tab=tab,
            sector_kind=sector_kind,
        )


def open_market_industry_filter(win: AshareMainWindow, industry: str) -> None:
    industry = str(industry or "").strip()
    if not industry:
        return
    nav_index = nav_index_for_key(win, "market")
    if nav_index is None:
        return
    show_page_by_key(win, "market", nav_index=nav_index)
    widget = win._page_widgets.get("market")
    if widget is None or not hasattr(widget, "page"):
        return
    widget.page.open_industry_drilldown(industry)


def open_market_concept_drilldown(win: AshareMainWindow, concept_name: str, vt_symbols: list[str]) -> None:
    label = str(concept_name or "").strip()
    if not label or not vt_symbols:
        return
    nav_index = nav_index_for_key(win, "market")
    if nav_index is None:
        return
    show_page_by_key(win, "market", nav_index=nav_index)
    widget = win._page_widgets.get("market")
    if widget is None or not hasattr(widget, "page"):
        return
    widget.page.open_concept_drilldown(label, vt_symbols)


def open_radar_card(
    win: AshareMainWindow,
    card_id: str,
    *,
    variant: str | None = None,
    refresh: bool = True,
) -> None:
    nav_index = nav_index_for_key(win, "radar")
    if nav_index is None:
        return
    show_page_by_key(win, "radar", nav_index=nav_index)

    def _open_card() -> None:
        widget = win._page_widgets.get("radar")
        if widget is None or not hasattr(widget, "page"):
            return
        controller = getattr(widget.page, "_radar_controller", None)
        if controller is None or not hasattr(controller, "open_external_card"):
            return
        controller.open_external_card(card_id, variant=variant, refresh=refresh)

    QtCore.QTimer.singleShot(0, _open_card)


def open_radar_leader_loop(win: AshareMainWindow, *, run_leader_screen: bool = False, leader_variant: str = "mainline") -> None:
    open_radar_card(win, "leader_pick", refresh=True)
    if run_leader_screen:
        open_screener_leader_screen(win, variant=leader_variant)


def focus_watchlist_symbol(win: AshareMainWindow, symbol: str, exchange_name: str) -> None:
    index = nav_index_for_key(win, "watchlist")
    if index is None:
        return
    try:
        exchange = Exchange[exchange_name]
    except KeyError:
        return
    win._show_page(index)
    widget = win._page_widgets.get("watchlist")
    if widget is None or not hasattr(widget, "page"):
        return
    page = widget.page
    page._select_stock_key((symbol, exchange))
    page.activate()
    if page.config.show_stock_notes and hasattr(page, "stock_note_panel"):
        page.stock_note_panel.expand()
