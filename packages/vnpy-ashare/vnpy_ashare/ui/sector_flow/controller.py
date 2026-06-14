"""板块资金监控控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.event import Event
from vnpy.trader.ui import QtCore

from vnpy_ashare.app.engine_access import get_quote_service
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.domain.market_hours import ashare_market_phase_label, is_ashare_trading_session
from vnpy_ashare.domain.sector_flow import SectorFlowSnapshot
from vnpy_ashare.services.sector_flow_service import SectorFlowService
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
        self._retired: list[QtCore.QThread] = []
        self._last_snapshot: SectorFlowSnapshot | None = None
        self._pending_focus: set[str] = set()
        self._service: SectorFlowService | None = None

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._session_timer = QtCore.QTimer(self)
        self._session_timer.setInterval(30_000)
        self._session_timer.timeout.connect(self._on_session_tick)

        panel = self._panel
        panel.refresh_requested.connect(self.refresh)
        panel.ai_requested.connect(self._request_ai)
        panel.table.sector_activated.connect(self._on_sector_activated)

    def _get_service(self) -> SectorFlowService | None:
        if self._service is not None:
            return self._service
        from vnpy_ashare.app.engine_access import get_sector_flow_service

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

    def refresh(self) -> None:
        service = self._get_service()
        if service is None:
            page_notify(self._page, "Ashare 引擎未就绪", level="warning")
            return
        if thread_is_active(self._worker):
            return
        worker = SectorFlowLoadWorker(service, parent=self._page)
        self._worker = worker
        self._panel.set_loading(True)
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

    def focus_sectors(self, sector_ids: list[str]) -> None:
        cleaned = {name.strip() for name in sector_ids if name and name.strip()}
        if not cleaned:
            return
        if self._last_snapshot and self._last_snapshot.rows:
            self._panel.focus_sectors(cleaned)
        else:
            self._pending_focus = cleaned
            self.refresh()

    def _on_sector_activated(self, industry: str) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_market_industry_filter"):
            page_notify(self._page, "无法打开市场页行业筛选", level="warning")
            return
        host.open_market_industry_filter(industry)

    def _find_main_window(self):
        widget = self._page
        while widget is not None:
            if hasattr(widget, "open_market_industry_filter"):
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
            extra_lines.append(f"净流入 {snap.top_inflow_name} {snap.top_inflow_yi:+.1f}亿；净流出 {snap.top_outflow_name} {snap.top_outflow_yi:+.1f}亿")
            for row in snap.rows[:8]:
                extra_lines.append(f"{row.name} 强度{row.strength:.1f} 涨幅{row.change_pct:+.2f}% 主力{row.net_flow_yi:+.2f}亿({row.flow_source})")
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
        lines = [
            "请解读当前板块资金结构：哪些行业资金净流入/流出突出，与涨幅是否一致，短线需关注什么。",
            "数据为行业聚合，主力列可能为日频或估算口径，请说明不确定性。",
        ]
        for row in snap.rows[:12]:
            lines.append(f"- {row.name}：强度{row.strength:.1f}，涨幅{row.change_pct:+.2f}%，主力净额{row.net_flow_yi:+.2f}亿（{row.flow_source}）")
        self._event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt="\n".join(lines), source_page="板块资金"),
            )
        )
