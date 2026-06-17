"""板块资金监控控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.app.engine_access import get_quote_service, get_sector_flow_service
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.domain.market.sector_flow import SectorConstituentRow, SectorFlowHistoryPoint, SectorFlowRow, SectorFlowSnapshot
from vnpy_ashare.domain.time.market_hours import ashare_market_phase_label, is_ashare_trading_session
from vnpy_ashare.services.sector_flow import SectorFlowService
from vnpy_ashare.ui.sector_flow.leaders_worker import SectorLeadersLoadWorker
from vnpy_ashare.ui.sector_flow.worker import SectorFlowLoadWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy.event import EventEngine
    from vnpy.trader.engine import MainEngine

    from vnpy_ashare.ui.sector_flow.page import SectorFlowPageWidget

_DEFAULT_REFRESH_MS = 30_000


class SectorFlowController(QtCore.QObject):
    def __init__(self, page: SectorFlowPageWidget, main_engine: MainEngine, event_engine: EventEngine) -> None:
        super().__init__(page)
        self._page = page
        self._main_engine = main_engine
        self._event_engine = event_engine
        self._panel = page.panel
        self._worker: SectorFlowLoadWorker | None = None
        self._leaders_worker: SectorLeadersLoadWorker | None = None
        self._retired: list[QtCore.QThread] = []
        self._last_snapshot: SectorFlowSnapshot | None = None
        self._pending_focus: set[str] = set()
        self._sector_kind = "industry"
        self._service: SectorFlowService | None = None

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._session_timer = QtCore.QTimer(self)
        self._session_timer.setInterval(30_000)
        self._session_timer.timeout.connect(self._on_session_tick)

        panel = self._panel
        panel.refresh_requested.connect(self.refresh)
        panel.ai_requested.connect(self._request_ai)
        panel.sector_kind_changed.connect(self._on_sector_kind_changed)
        panel.table.sector_activated.connect(self._on_sector_activated)
        panel.table.sector_selected.connect(self._on_sector_selected)
        panel.detail.market_drilldown_requested.connect(self._on_detail_market_drilldown)
        panel.detail.screener_requested.connect(self._on_detail_screener)
        panel.detail.resonance_screener_requested.connect(self._on_detail_resonance_screener)
        panel.screener_requested.connect(self._on_screener_requested)

    def _get_service(self) -> SectorFlowService | None:
        if self._service is not None:
            return self._service

        service = get_sector_flow_service(self._main_engine)
        if service is not None:
            self._service = service
        return service

    def activate(self) -> None:
        self._publish_ai_context()
        self.refresh()
        self._schedule_timer()
        self._session_timer.start()

    def deactivate(self) -> None:
        self._timer.stop()
        self._session_timer.stop()
        if self._worker is not None:
            self._worker.request_cancel()
            release_thread(self._retired, self._worker, timeout_ms=0)
            self._worker = None
        if self._leaders_worker is not None:
            release_thread(self._retired, self._leaders_worker, timeout_ms=0)
            self._leaders_worker = None

    def refresh(self) -> None:
        service = self._get_service()
        if service is None:
            page_notify(self._page, "Ashare 引擎未就绪", level="warning")
            return
        if thread_is_active(self._worker):
            return
        worker = SectorFlowLoadWorker(service, sector_kind=self._sector_kind, parent=self._page)
        self._worker = worker
        loading_message = "正在加载概念板块资金…" if self._sector_kind == "concept" else "正在加载行业板块资金…"
        self._panel.set_loading(True, message=loading_message)
        self._page.set_status(loading_message)
        worker.finished.connect(self._on_loaded)
        worker.failed.connect(self._on_failed)
        worker.finished.connect(lambda _snap, w=worker: self._release_worker(w))
        worker.failed.connect(lambda _msg, w=worker: self._release_worker(w))
        worker.start()

    def _release_worker(self, worker: SectorFlowLoadWorker) -> None:
        if self._worker is worker:
            self._worker = None
        release_thread(self._retired, worker)

    def _on_loaded(self, snapshot: SectorFlowSnapshot) -> None:
        self._panel.set_loading(False)
        if not snapshot.rows:
            self._panel.apply_snapshot(snapshot)
            self._panel.detail.clear()
            status = snapshot.empty_hint or snapshot.updated_at or "暂无数据"
            self._page.set_status(status)
            return
        self._last_snapshot = snapshot
        self._panel.apply_snapshot(snapshot)
        if self._pending_focus:
            self._panel.focus_sectors(self._pending_focus)
            self._pending_focus.clear()
        self._update_status_label()
        self._publish_ai_context(snapshot)
        first_row = self._panel.table.selected_sector_row()
        if first_row is None and snapshot.inflow_rows:
            self._panel.table.selectRow(0)
            first_row = self._panel.table.selected_sector_row()
        if first_row is not None:
            self._load_sector_leaders(first_row)

    def _on_sector_selected(self, sector: SectorFlowRow) -> None:
        self._load_sector_leaders(sector)

    def _load_sector_leaders(self, sector: SectorFlowRow) -> None:
        service = self._get_service()
        if service is None:
            return
        if thread_is_active(self._leaders_worker):
            return
        self._panel.detail.set_loading(sector.name)
        worker = SectorLeadersLoadWorker(service, sector, parent=self._page)
        self._leaders_worker = worker
        worker.finished.connect(self._on_leaders_loaded)
        worker.finished.connect(lambda _sector, _result, _history, w=worker: self._release_leaders_worker(w))
        worker.start()

    def _release_leaders_worker(self, worker: SectorLeadersLoadWorker) -> None:
        if self._leaders_worker is worker:
            self._leaders_worker = None
        release_thread(self._retired, worker)

    def _on_leaders_loaded(self, sector: SectorFlowRow, result: object, history: object) -> None:

        if isinstance(result, Exception):
            self._panel.detail.show_sector(sector, [], history=[] if not isinstance(history, list) else history)
            return
        leaders = result if isinstance(result, list) else []
        typed: list[SectorConstituentRow] = [item for item in leaders if isinstance(item, SectorConstituentRow)]
        history_rows: list[SectorFlowHistoryPoint] = [
            item for item in (history if isinstance(history, list) else []) if isinstance(item, SectorFlowHistoryPoint)
        ]
        self._panel.detail.show_sector(sector, typed, history=history_rows)

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
            host.open_market_industry_filter(sector.name)
            return
        page_notify(self._page, "无法打开市场页行业筛选", level="warning")

    def _on_detail_screener(self, industry: str) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_screener_industry"):
            page_notify(self._page, "无法打开选股页", level="warning")
            return
        host.open_screener_industry(industry)

    def _on_detail_resonance_screener(self) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_screener_radar_resonance"):
            page_notify(self._page, "无法打开共振选股", level="warning")
            return
        host.open_screener_radar_resonance()

    def _update_status_label(self) -> None:
        phase = ashare_market_phase_label()
        hint = "盘中约30秒刷新" if is_ashare_trading_session() else "非交易时段，已暂停自动刷新"
        self._page.set_status(f"{hint} · 当前{phase}")

    def _on_session_tick(self) -> None:
        self._schedule_timer()
        self._update_status_label()

    def _on_failed(self, message: str) -> None:
        self._panel.set_loading(False)
        page_notify(self._page, f"板块资金加载失败：{message}", level="warning")
        self._page.set_status(message)

    def _schedule_timer(self) -> None:
        if is_ashare_trading_session():
            self._timer.start(_DEFAULT_REFRESH_MS)
        else:
            self._timer.stop()

    def _on_sector_kind_changed(self, sector_kind: str) -> None:
        self._sector_kind = sector_kind
        self._last_snapshot = None
        self.refresh()

    def focus_sectors(self, sector_ids: list[str]) -> None:
        cleaned = {name.strip() for name in sector_ids if name and name.strip()}
        if not cleaned:
            return
        self._sector_kind = "industry"
        self._panel.select_sector_kind("industry")
        if self._last_snapshot and self._last_snapshot.rows and self._last_snapshot.sector_kind == "industry":
            self._panel.focus_sectors(cleaned)
        else:
            self._pending_focus = cleaned
            self.refresh()

    def _on_sector_activated(self, industry: str) -> None:
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
        host.open_market_industry_filter(industry)

    def _on_screener_requested(self) -> None:
        if self._sector_kind != "industry":
            page_notify(self._page, "成分选股仅支持行业板块", level="warning")
            return
        industry = self._panel.table.selected_industry()
        if not industry:
            page_notify(self._page, "请先在表格中选中一个行业", level="warning")
            return
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_screener_industry"):
            page_notify(self._page, "无法打开选股页", level="warning")
            return
        host.open_screener_industry(industry)

    def _find_main_window(self) -> QtWidgets.QWidget | None:
        widget: QtWidgets.QWidget | None = self._page
        while widget is not None:
            if hasattr(widget, "open_market_industry_filter") or hasattr(widget, "open_market_concept_drilldown") or hasattr(widget, "open_screener_industry"):
                return widget
            widget = widget.parentWidget()
        return None

    def _publish_ai_context(self, snapshot: SectorFlowSnapshot | None = None) -> None:
        quote_service = get_quote_service(self._main_engine)
        if quote_service is None:
            return
        extra_lines = ["板块资金监控页"]
        snap = snapshot or self._last_snapshot
        if snap and snap.rows:
            kind_label = "概念" if snap.sector_kind == "concept" else "行业"
            mode_labels = {"intraday": "盘中估算", "official_dc": "日终东财", "official_ths": "日终同花顺"}
            extra_lines.append(f"{kind_label}·{mode_labels.get(snap.data_mode, snap.data_mode)}")
            extra_lines.append(f"净流入 {snap.top_inflow_name} {snap.top_inflow_yi:+.1f}亿；净流出 {snap.top_outflow_name} {snap.top_outflow_yi:+.1f}亿")
            for row in snap.rows[:8]:
                leader = f" 龙头{row.leader_stock}" if row.leader_stock else ""
                extra_lines.append(f"{row.name} 强度{row.strength:.1f} 涨幅{row.change_pct:+.2f}% 主力{row.net_flow_yi:+.2f}亿({row.flow_source}){leader}")
        quote_service.publish_quote_context(
            page="板块资金",
            signal_extra="\n".join(extra_lines),
        )

    def _request_ai(self) -> None:
        snap = self._last_snapshot
        if snap is None or not snap.rows:
            page_notify(self._page, "请先刷新板块数据", level="warning")
            return
        if self._event_engine is None:
            return
        kind_label = "概念" if snap.sector_kind == "concept" else "行业"
        mode_note = {
            "intraday": "盘中为行情聚合估算",
            "official_dc": "东财官方日终板块资金",
            "official_ths": "同花顺官方日终概念资金",
        }.get(snap.data_mode, "")
        lines = [
            f"请解读当前{kind_label}板块资金结构：哪些板块资金净流入/流出突出，与涨幅是否一致，短线需关注什么。",
            f"数据口径：{mode_note}，请说明不确定性。",
        ]
        for row in snap.rows[:12]:
            leader = f"，龙头 {row.leader_stock}" if row.leader_stock else ""
            lines.append(f"- {row.name}：强度{row.strength:.1f}，涨幅{row.change_pct:+.2f}%，主力净额{row.net_flow_yi:+.2f}亿（{row.flow_source}）{leader}")
        self._event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt="\n".join(lines), source_page="板块资金"),
            )
        )
