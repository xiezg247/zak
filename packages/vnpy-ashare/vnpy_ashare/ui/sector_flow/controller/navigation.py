"""板块资金页深链导航（市场 / 选股 / 雷达）。"""

from __future__ import annotations

from vnpy.trader.ui import QtWidgets

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow
from vnpy_ashare.ui.quotes.market_overview.industry_filter_combo import resolve_industry_for_drilldown
from vnpy_ashare.ui.sector_flow.controller.base import (
    TAB_DIVERGENCE,
    TAB_INFLOW,
    TAB_OUTFLOW,
    TAB_OUTLOOK,
    TAB_OVERVIEW,
    TAB_ROTATION,
    SectorFlowControllerBase,
)
from vnpy_common.ui.feedback import page_notify


class SectorFlowNavigationMixin(SectorFlowControllerBase):
    def _on_detail_market_drilldown(self, sector: SectorFlowRow) -> None:
        host = self._find_main_window()
        if host is None:
            page_notify(self._page, "无法打开市场页", level="warning")
            return
        if sector.sector_kind == "concept":
            service = self._get_service()
            if service is None or not hasattr(host, "open_market_concept_drilldown"):
                page_notify(self._page, "无法打开市场页概念筛选", level="warning")
                return
            vt_symbols = service.resolve_concept_vt_symbols(sector)
            if not vt_symbols:
                page_notify(self._page, f"未找到概念「{sector.name}」成分映射", level="warning")
                return
            host.open_market_concept_drilldown(sector.name, vt_symbols)
            return
        if hasattr(host, "open_market_industry_filter"):
            industry = (
                resolve_industry_for_drilldown(
                    sector.name,
                    sector_id=sector.sector_id,
                )
                or str(sector.name or "").strip()
            )
            if not industry:
                page_notify(self._page, f"未找到行业「{sector.name}」映射", level="warning")
                return
            host.open_market_industry_filter(industry)
            return
        page_notify(self._page, "无法打开市场页行业筛选", level="warning")

    def _on_detail_screener(self, industry: str) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_screener_industry"):
            page_notify(self._page, "无法打开选股页", level="warning")
            return
        host.open_screener_industry(industry)

    def _on_detail_radar_leader(self) -> None:
        sector = self._panel.detail.current_sector()
        if sector is None:
            return
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_radar_card"):
            page_notify(self._page, "无法打开雷达页", level="warning")
            return
        host.open_radar_card("leader_pick", refresh=True)
        self._page.set_status(f"已打开雷达·龙头 · {sector.name}")

    def _on_detail_radar_sector_theme(self) -> None:
        sector = self._panel.detail.current_sector()
        if sector is None or sector.sector_kind != "industry":
            return
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_radar_card"):
            page_notify(self._page, "无法打开雷达页", level="warning")
            return
        host.open_radar_card("sector_theme", variant="leaders_tiered", refresh=True)
        self._page.set_status(f"已打开雷达·主线 · {sector.name}")

    def _on_detail_leader_screen(self) -> None:
        sector = self._panel.detail.current_sector()
        if sector is None:
            return
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_radar_leader_loop"):
            page_notify(self._page, "无法打开龙头选股", level="warning")
            return
        host.open_radar_leader_loop(run_leader_screen=True)
        self._page.set_status(f"已打开龙头选股 · {sector.name}")

    def focus_sectors(
        self,
        sector_ids: list[str],
        *,
        tab: str = "default",
        sector_kind: str | None = None,
    ) -> None:
        cleaned = {name.strip() for name in sector_ids if name and name.strip()}
        tab_map = {
            "default": TAB_OVERVIEW,
            "overview": TAB_OVERVIEW,
            "inflow": TAB_INFLOW,
            "outflow": TAB_OUTFLOW,
            "divergence": TAB_DIVERGENCE,
            "rotation": TAB_ROTATION,
            "outlook": TAB_OUTLOOK,
        }
        pending_tab = tab_map.get(tab, TAB_OVERVIEW)
        self._pending_view_tab = pending_tab
        if sector_kind in {"industry", "concept"}:
            self._sector_kind = sector_kind
            self._panel.select_sector_kind(sector_kind, emit=False)
        elif tab not in {"rotation", "outlook"}:
            self._sector_kind = "industry"
            self._panel.select_sector_kind("industry", emit=False)
        if cleaned:
            self._pending_focus = cleaned
        if self._last_snapshot and self._last_snapshot.rows and self._last_snapshot.sector_kind == self._sector_kind:
            self._panel.select_view_tab(pending_tab, emit=True)
            if cleaned:
                self._panel.focus_sectors(cleaned)
            return
        self.refresh()

    def _on_sector_activated(self, industry: str) -> None:
        if self._panel.active_tab == TAB_ROTATION:
            sector = self._panel.rotation_table.selected_sector_row()
        elif self._panel.active_tab == TAB_OUTLOOK:
            sector = self._panel.outlook_table.selected_sector_row()
        else:
            sector = self._panel.table.selected_sector_row()
        if sector is not None and sector.sector_kind == "concept":
            self._on_detail_market_drilldown(sector)
            return
        if self._sector_kind == "concept":
            page_notify(self._page, "概念板块请使用右侧「市场成分」或单击选中后操作", level="info")
            return
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_market_industry_filter"):
            page_notify(self._page, "无法打开市场页行业筛选", level="warning")
            return
        if sector is not None and sector.sector_kind == "industry":
            label = resolve_industry_for_drilldown(sector.name, sector_id=sector.sector_id) or sector.name
        else:
            label = resolve_industry_for_drilldown(industry) or industry
        if not label:
            page_notify(self._page, f"未找到行业「{industry}」映射", level="warning")
            return
        host.open_market_industry_filter(label)

    def _find_main_window(self) -> QtWidgets.QWidget | None:
        widget: QtWidgets.QWidget | None = self._page
        while widget is not None:
            if (
                hasattr(widget, "open_market_industry_filter")
                or hasattr(widget, "open_market_concept_drilldown")
                or hasattr(widget, "open_screener_industry")
                or hasattr(widget, "open_radar_card")
            ):
                return widget
            widget = widget.parentWidget()
        return None
