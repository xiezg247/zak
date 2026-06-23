"""市场页行业 / 概念下钻筛选（板块资金入口）。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.quotes.rank.rank_catalog import get_rank_definition
from vnpy_ashare.ui.quotes.features.market_rank import SECTOR_DRILLDOWN_RANK_ID

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage


def set_market_industry_filter(page: QuotesPage, industry: str | None) -> None:
    page._market_industry_filter = industry
    if industry:
        page._market_vt_whitelist = None
        page._market_drilldown_label = None
    listener = page._market_industry_filter_listener
    if listener is not None:
        listener(industry)
    page._table.filter_market_display()


def clear_market_drilldown_filters(page: QuotesPage) -> None:
    page._market_industry_filter = None
    page._market_vt_whitelist = None
    page._market_drilldown_label = None
    listener = page._market_industry_filter_listener
    if listener is not None:
        listener(None)
    page._table.filter_market_display()


def apply_pending_market_drilldown(page: QuotesPage) -> bool:
    """将 open_industry/concept_drilldown 的 pending 筛选落盘。返回是否处理了 pending。"""
    pending_concept = page._pending_concept_drilldown
    pending_industry = page._pending_industry_drilldown
    if not pending_concept and not pending_industry:
        return False
    page._pending_concept_drilldown = None
    page._pending_industry_drilldown = None
    if pending_concept:
        page._market_vt_whitelist = pending_concept
        page._market_industry_filter = None
        listener = page._market_industry_filter_listener
        if listener is not None:
            listener(None)
    else:
        page._market_vt_whitelist = None
        page._market_drilldown_label = None
        page._market_industry_filter = pending_industry
        listener = page._market_industry_filter_listener
        if listener is not None:
            listener(pending_industry)
    page._industry_map_cache = None
    page._market_board_base = None
    page._market_board_base_key = None
    return True


def open_industry_drilldown(page: QuotesPage, industry: str, *, rank_id: str = "net_mf_in") -> None:
    """从板块资金等入口下钻：主力净流入榜 + 行业成分筛选。"""
    from vnpy_ashare.ui.quotes.market_overview.industry_filter_combo import resolve_industry_for_drilldown

    cleaned = resolve_industry_for_drilldown(industry) or str(industry or "").strip()
    if not cleaned:
        return
    page._pending_concept_drilldown = None
    target_rank = get_rank_definition(rank_id or SECTOR_DRILLDOWN_RANK_ID).id
    page._pending_industry_drilldown = cleaned
    page.search_edit.clear()
    page._market_filter_keyword = ""
    if page.config.use_market_rank:
        page._market_rank.apply_rank_for_drilldown(target_rank)
    else:
        set_market_industry_filter(page, cleaned)
        page._pending_industry_drilldown = None
    rank_title = get_rank_definition(target_rank).title
    page.status_label.setText(f"{rank_title} · 行业筛选：{cleaned}（来自板块资金，点击行业 × 可清除）")


def open_concept_drilldown(
    page: QuotesPage,
    concept_name: str,
    vt_symbols: list[str],
    *,
    rank_id: str = "net_mf_in",
) -> None:
    """从板块资金概念 Tab 下钻：主力净流入榜 + 概念成分白名单。"""
    label = str(concept_name or "").strip()
    cleaned = {str(item).strip() for item in vt_symbols if str(item or "").strip()}
    if not label or not cleaned:
        return
    page._pending_industry_drilldown = None
    target_rank = get_rank_definition(rank_id or SECTOR_DRILLDOWN_RANK_ID).id
    page._pending_concept_drilldown = frozenset(cleaned)
    page._market_drilldown_label = f"概念：{label}"
    page.search_edit.clear()
    page._market_filter_keyword = ""
    if page.config.use_market_rank:
        page._market_rank.apply_rank_for_drilldown(target_rank)
    else:
        page._market_vt_whitelist = page._pending_concept_drilldown
        page._pending_concept_drilldown = None
        set_market_industry_filter(page, None)
    rank_title = get_rank_definition(target_rank).title
    page.status_label.setText(f"{rank_title} · {page._market_drilldown_label}（来自板块资金）")
