"""雷达页控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.app.engine_access import get_watchlist_service
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import OUTLOOK_SIGNAL_CARD_IDS, save_outlook_strategy_class
from vnpy_ashare.quotes.radar.predict.predict_prefs import load_predict_model_mode, save_predict_model_mode
from vnpy_ashare.quotes.radar.radar_board_store import set_radar_board_snapshot
from vnpy_ashare.quotes.radar.radar_catalog import (
    DEFAULT_LEADER_PICK_VARIANT,
    DEFAULT_LIMIT_LADDER_VARIANT,
    DEFAULT_SCENARIO_VARIANT,
    DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    DEFAULT_SECTOR_VARIANT,
    RADAR_CARD_BY_ID,
    auto_refresh_card_ids,
    full_refresh_every_n_ticks,
    list_radar_cards,
    list_radar_cards_for_group,
    list_radar_cards_for_mode,
    radar_card_group,
)
from vnpy_ashare.quotes.radar.radar_full_refresh_prefs import save_radar_full_refresh_every
from vnpy_ashare.quotes.radar.radar_horizon import OUTLOOK_FORCE_RECOMPUTE_CARD_IDS
from vnpy_ashare.quotes.radar.radar_loaders import (
    RadarCardData,
    build_eod_leader_prompt,
    build_radar_ai_prompt,
    build_radar_card_ai_prompt,
    build_radar_resonance_ai_prompt,
    build_radar_resonance_list,
    collect_radar_risk_vt_symbols,
    compute_radar_resonance,
)
from vnpy_ashare.quotes.radar.radar_resonance_prefs import DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS
from vnpy_ashare.quotes.radar.radar_resonance_store import set_radar_resonance_entries
from vnpy_ashare.quotes.radar.radar_snapshot import (
    build_radar_board_snapshot,
    enrich_resonance_entries,
    row_lookup_from_payload,
)
from vnpy_ashare.services.watchlist_short_term import (
    add_rows_to_watchlist_pool,
    add_short_term_focus,
    collect_dragon_1_rows,
    resonance_entries_to_rows,
)
from vnpy_ashare.trading.plan.propose import _next_trade_date
from vnpy_ashare.ui.features.stock_analysis.open import show_stock_analysis_from_quotes_page
from vnpy_ashare.ui.quotes.page.config import save_radar_card_refresh_ms
from vnpy_ashare.ui.quotes.radar.resonance_weight_dialog import RadarResonanceWeightDialog
from vnpy_ashare.ui.quotes.radar.worker import RadarCardLoadWorker
from vnpy_ashare.ui.quotes.watchlist_positions.plan_dialog import TradingPlanDialog
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage
    from vnpy_ashare.ui.quotes.radar.card import RadarBoard
    from vnpy_ashare.ui.quotes.radar.resonance_panel import RadarResonancePanel

_RADAR_CARD_REFRESH_STAGGER_MS = 80
_RADAR_RESONANCE_SYNC_DEBOUNCE_MS = 80


class RadarController(QtCore.QObject):
    def __init__(
        self,
        page: QuotesPage,
        board: RadarBoard,
        *,
        resonance_panel: RadarResonancePanel | None = None,
    ) -> None:
        super().__init__(page)
        self._page = page
        self._board = board
        self._resonance_panel = resonance_panel
        self._card_workers: dict[str, RadarCardLoadWorker] = {}
        self._retired_workers: list[QtCore.QThread] = []
        self._sector_variant = DEFAULT_SECTOR_VARIANT
        self._card_variants: dict[str, str] = {
            "sector_theme": DEFAULT_SECTOR_VARIANT,
            "leader_pick": DEFAULT_LEADER_PICK_VARIANT,
            "discovery_limit_ladder": DEFAULT_LIMIT_LADDER_VARIANT,
            "outlook_scenario": DEFAULT_SCENARIO_VARIANT,
            "outlook_predict": load_predict_model_mode(),
        }
        self._last_payload: dict[str, RadarCardData] = {}
        self._cached_resonance: dict[str, int] = {}
        self._auto_refresh_ticks: dict[str, int] = {}
        self._auto_refresh_timers: dict[str, QtCore.QTimer] = {}
        self._refresh_queue: list[tuple[str, dict[str, object]]] = []
        self._refresh_stagger_timer = QtCore.QTimer(self)
        self._refresh_stagger_timer.setSingleShot(True)
        self._refresh_stagger_timer.timeout.connect(self._dequeue_refresh)
        self._resonance_sync_timer = QtCore.QTimer(self)
        self._resonance_sync_timer.setSingleShot(True)
        self._resonance_sync_timer.setInterval(_RADAR_RESONANCE_SYNC_DEBOUNCE_MS)
        self._resonance_sync_timer.timeout.connect(self._flush_resonance_sync)
        self._session_timer = QtCore.QTimer(self)
        self._session_timer.setInterval(30_000)
        self._session_timer.timeout.connect(self._on_session_tick)
        self._setup_auto_refresh_timers()

        board.variant_changed.connect(self._on_variant_changed)
        board.row_activated.connect(self._on_row_activated)
        board.add_watchlist_requested.connect(self._on_add_watchlist)
        board.batch_add_watchlist_requested.connect(self._on_batch_add_watchlist)
        board.stock_analysis_requested.connect(self._on_stock_analysis)
        board.view_run_requested.connect(self._on_view_run)
        board.sector_flow_requested.connect(self._on_sector_flow)
        board.sector_rotation_requested.connect(self._on_sector_rotation)
        board.refresh_requested.connect(self._on_card_refresh_requested)
        board.quote_refresh_requested.connect(self._on_card_quote_refresh_requested)
        board.ai_requested.connect(self.request_card_ai)
        board.auto_refresh_changed.connect(self._on_auto_refresh_changed)
        board.full_refresh_interval_changed.connect(self._on_full_refresh_interval_changed)
        board.mode_changed.connect(self._on_board_mode_changed)
        board.group_changed.connect(self._on_board_group_changed)
        board.outlook_strategy_changed.connect(self._on_outlook_strategy_changed)

        panel = self._resonance_panel
        if panel is not None:
            panel.row_activated.connect(self._on_row_activated)
            panel.add_watchlist_requested.connect(self._on_add_watchlist)
            panel.batch_add_watchlist_requested.connect(self._on_resonance_batch_add_watchlist)
            panel.add_dragon_watchlist_requested.connect(self._on_resonance_dragon_watchlist)
            panel.stock_analysis_requested.connect(self._on_stock_analysis)
            panel.ai_resonance_requested.connect(self.request_resonance_ai_summary)
            panel.propose_trading_plan_requested.connect(self._on_propose_trading_plan)
            panel.eod_leader_ai_requested.connect(self.request_eod_leader_ai)
            panel.open_screener_requested.connect(self._on_open_screener_resonance)
            panel.open_leader_screener_requested.connect(self._on_open_screener_leader)
            panel.resonance_weights_requested.connect(self._on_resonance_weights_requested)
            panel.add_short_term_focus_requested.connect(self._on_resonance_short_term_focus)

    def _on_open_screener_resonance(self) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_screener_radar_resonance"):
            page_notify(self._page, "无法打开选股页", level="warning")
            return
        host.open_screener_radar_resonance()

    def _on_propose_trading_plan(self) -> None:
        dialog = TradingPlanDialog(
            page=self._page,
            parent=self._page,
            trade_date=_next_trade_date(),
            auto_draft=True,
        )
        dialog.exec()

    def _on_open_screener_leader(self, *, focus: bool = True) -> None:
        if focus:
            self._board.focus_card("leader_pick")
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_screener_leader_screen"):
            page_notify(self._page, "无法打开选股页", level="warning")
            return
        variant = self._card_variants.get("leader_pick", DEFAULT_LEADER_PICK_VARIANT)
        host.open_screener_leader_screen(variant=variant)

    def open_leader_shortcut(self) -> None:
        """顶栏「选龙头」：定位龙头卡并打开选股 Hub 执行。"""
        self._board.focus_card("leader_pick")
        self.refresh_card("leader_pick")
        self._on_open_screener_leader(focus=False)

    def open_external_card(
        self,
        card_id: str,
        *,
        variant: str | None = None,
        refresh: bool = True,
    ) -> bool:
        """外部入口（板块资金页等）定位卡片并可选刷新。"""
        if variant and card_id in self._card_variants:
            self._card_variants[card_id] = variant
            if card_id == "sector_theme":
                self._sector_variant = variant
            card_widget = self._board.card(card_id)
            if card_widget is not None:
                card_widget.set_variant_key(variant)
        focused = self._board.focus_card(card_id)
        if refresh and focused:
            self.refresh_card(card_id)
        return focused

    def _on_resonance_weights_requested(self) -> None:
        dialog = RadarResonanceWeightDialog(self._page)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        dialog.save()
        if not self._last_payload:
            page_notify(self._page, "请先刷新雷达卡片", level="warning")
            return
        resonance = compute_radar_resonance(self._last_payload)
        self._board.apply_board(self._last_payload)
        self._board.sync_resonance(resonance)
        self._sync_resonance_panel()
        self._update_status(resonance=resonance)
        self._reload_cards_after_resonance_weight_change()
        page_notify(self._page, "共振权重已更新，相关卡片正在重载")

    def _reload_cards_after_resonance_weight_change(self) -> None:
        """权重变更后全量重算发现 / 板块 / 自选等指标卡（保留展望等缓存卡）。"""
        reload_ids = [card_id for card_id in DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS if card_id in self._last_payload and not card_id.startswith("outlook_")]
        for card_id in reload_ids:
            self._enqueue_refresh(card_id, force_recompute=True)

    def activate(self) -> None:
        self.activate_light()
        self.activate_heavy()

    def activate_light(self) -> None:
        """切页首帧：仅同步 Tab / 策略下拉等 UI 状态。"""
        predict_mode = load_predict_model_mode()
        self._card_variants["outlook_predict"] = predict_mode
        predict_card = self._board.card("outlook_predict")
        if predict_card is not None:
            predict_card.set_variant_key(predict_mode)
        self._board.update_tab_badges()
        self._sync_resonance_tab_from_board()
        self._page._refresh_emotion_cycle_chip()

    def activate_heavy(self) -> None:
        """延后执行：刷新当前分组卡片并启动自动轮询。"""
        self.refresh_current_group()
        self._start_auto_refresh()
        self._session_timer.start()

    def deactivate(self) -> None:
        self._session_timer.stop()
        self._stop_auto_refresh()
        self._cancel_all_workers()
        self._refresh_queue.clear()
        self._refresh_stagger_timer.stop()
        self._resonance_sync_timer.stop()

    def _setup_auto_refresh_timers(self) -> None:
        for card_id in auto_refresh_card_ids():
            timer = QtCore.QTimer(self)
            timer.timeout.connect(lambda card_id=card_id: self._on_auto_refresh_card(card_id))
            self._auto_refresh_timers[card_id] = timer

    def _start_auto_refresh(self) -> None:
        self._board.sync_mode_badges()
        for card_id in auto_refresh_card_ids():
            self._apply_card_auto_refresh(card_id)
        self._page._update_refresh_hint_label()

    def _on_session_tick(self) -> None:
        self._board.sync_mode_badges()
        for card_id in auto_refresh_card_ids():
            self._apply_card_auto_refresh(card_id)
        self._page._update_refresh_hint_label()

    def _stop_auto_refresh(self) -> None:
        for timer in self._auto_refresh_timers.values():
            timer.stop()
        self._page._update_refresh_hint_label()

    def _card_is_visible(self, card_id: str) -> bool:
        spec = RADAR_CARD_BY_ID.get(card_id)
        if spec is None:
            return False
        if spec.mode != self._board.current_mode():
            return False
        group_key = radar_card_group(card_id)
        return group_key is not None and group_key == self._board.current_group()

    def _apply_card_auto_refresh(self, card_id: str) -> None:
        timer = self._auto_refresh_timers.get(card_id)
        widget = self._board.card(card_id)
        if timer is None or widget is None:
            return
        if not self._card_is_visible(card_id):
            timer.stop()
            return
        ms = widget.auto_refresh_ms()
        if ms <= 0 or not is_ashare_trading_session():
            timer.stop()
            return
        timer.setInterval(max(int(ms), 1000))
        timer.start()

    def _on_auto_refresh_changed(self, card_id: str, ms: int) -> None:
        save_radar_card_refresh_ms(card_id, ms)
        self._apply_card_auto_refresh(card_id)
        self._page._update_refresh_hint_label()

    def _on_full_refresh_interval_changed(self, card_id: str, every_n: int) -> None:
        save_radar_full_refresh_every(card_id, every_n)
        self._auto_refresh_ticks[card_id] = 0

    def _on_auto_refresh_card(self, card_id: str) -> None:
        """自动刷新：多数周期仅更新现价 / 涨幅，周期性全量重算指标。"""
        existing = self._last_payload.get(card_id)
        if existing and existing.rows:
            tick = self._auto_refresh_ticks.get(card_id, 0) + 1
            self._auto_refresh_ticks[card_id] = tick
            if tick % full_refresh_every_n_ticks(card_id) != 0:
                self.refresh_card(card_id, force_recompute=False, quote_only=True)
                return
        self.refresh_card(card_id, force_recompute=False)

    def refresh(self) -> None:
        """错峰刷新全部卡片，避免多张卡同时完成时主线程拥堵。"""
        items = [(spec.id, {}) for spec in list_radar_cards()]
        self._enqueue_refresh_many(items)

    def refresh_current_group(self) -> None:
        """刷新当前分区下子 Tab 内的全部卡片。"""
        mode = self._board.current_mode()
        group_key = self._board.current_group(mode)
        items = [(spec.id, {}) for spec in list_radar_cards_for_group(mode, group_key)]
        self._enqueue_refresh_many(items)

    def refresh_current_mode(self) -> None:
        """刷新当前分区内的全部卡片（含各子 Tab）。"""
        items = [(spec.id, {}) for spec in list_radar_cards_for_mode(self._board.current_mode())]
        self._enqueue_refresh_many(items)

    def _enqueue_refresh(self, card_id: str, **kwargs: object) -> None:
        """批量刷新时错峰启动 worker，单卡手动刷新仍走 refresh_card。"""
        self._enqueue_refresh_many([(card_id, dict(kwargs))])

    def _enqueue_refresh_many(self, items: list[tuple[str, dict[str, object]]]) -> None:
        if not items:
            return
        kick = not self._refresh_queue and not self._refresh_stagger_timer.isActive()
        for card_id, kwargs in items:
            self._refresh_queue = [(cid, kw) for cid, kw in self._refresh_queue if cid != card_id]
            self._refresh_queue.append((card_id, kwargs))
        if kick:
            self._dequeue_refresh()

    def _dequeue_refresh(self) -> None:
        if not self._refresh_queue:
            return
        card_id, kwargs = self._refresh_queue.pop(0)
        self.refresh_card(card_id, **kwargs)
        if self._refresh_queue:
            self._refresh_stagger_timer.start(_RADAR_CARD_REFRESH_STAGGER_MS)

    def _on_outlook_strategy_changed(self, class_name: str) -> None:
        if not class_name:
            return
        save_outlook_strategy_class(class_name)
        for card_id in OUTLOOK_SIGNAL_CARD_IDS:
            self._enqueue_refresh(card_id, force_recompute=True)

    def _on_board_mode_changed(self, mode: str) -> None:
        self._sync_resonance_tab_from_board(mode)
        self._start_auto_refresh()
        self.refresh_current_group()

    def _on_board_group_changed(self, mode: str, _group_key: str) -> None:
        if mode != self._board.current_mode():
            return
        self._start_auto_refresh()
        self.refresh_current_group()

    def _sync_resonance_tab_from_board(self, mode: str | None = None) -> None:
        panel = self._resonance_panel
        if panel is None:
            return
        active_mode = mode or self._board.current_mode()
        if active_mode in ("statistical", "predictive"):
            panel.select_tab(active_mode)  # type: ignore[arg-type]

    def _on_card_refresh_requested(self, card_id: str) -> None:
        force = card_id in OUTLOOK_FORCE_RECOMPUTE_CARD_IDS
        self.refresh_card(card_id, force_recompute=force)

    def _on_card_quote_refresh_requested(self, card_id: str) -> None:
        self.refresh_card(card_id, force_recompute=False, quote_only=True)

    def refresh_card(
        self,
        card_id: str,
        *,
        force_recompute: bool = False,
        quote_only: bool = False,
    ) -> None:
        if thread_is_active(self._card_workers.get(card_id)):
            return
        existing = self._last_payload.get(card_id)
        if quote_only and (existing is None or not existing.rows):
            quote_only = False
        self._cancel_card_worker(card_id)
        worker = RadarCardLoadWorker(
            card_id=card_id,
            sector_variant=self._card_variants.get("sector_theme", DEFAULT_SECTOR_VARIANT),
            sector_flow_hot_variant=self._card_variants.get("sector_flow_hot", DEFAULT_SECTOR_FLOW_HOT_VARIANT),
            leader_pick_variant=self._card_variants.get("leader_pick", DEFAULT_LEADER_PICK_VARIANT),
            limit_ladder_variant=self._card_variants.get("discovery_limit_ladder", DEFAULT_LIMIT_LADDER_VARIANT),
            scenario_variant=self._card_variants.get("outlook_scenario", DEFAULT_SCENARIO_VARIANT),
            force_recompute=force_recompute,
            quote_only=quote_only,
            existing_data=existing if quote_only else None,
            parent=self._page,
        )
        self._card_workers[card_id] = worker
        worker.finished.connect(self._on_card_loaded)
        worker.failed.connect(self._on_card_failed)
        worker.finished.connect(lambda _card_id, _data, _quote_only, w=worker: self._release_worker(w))
        worker.failed.connect(lambda _card_id, _msg, w=worker: self._release_worker(w))
        widget = self._board.card(card_id)
        if widget is not None and not quote_only:
            widget.set_loading(True)
        self._update_status()
        worker.start()

    def request_ai_summary(self) -> None:
        if not self._last_payload:
            page_notify(self._page, "请先刷新雷达数据", level="warning")
            return
        if self._page.event_engine is None:
            page_notify(self._page, "AI 服务未就绪", level="warning")
            return
        prompt = build_radar_ai_prompt(self._last_payload)
        self._page.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt=prompt, source_page="雷达"),
            )
        )
        if hasattr(self._page, "status_label"):
            self._page.status_label.setText("已发送 AI 洞察请求")

    def request_card_ai(self, card_id: str) -> None:
        data = self._last_payload.get(card_id)
        if data is None:
            page_notify(self._page, "请先刷新该卡片", level="warning")
            return
        if self._page.event_engine is None:
            page_notify(self._page, "AI 服务未就绪", level="warning")
            return
        resonance = compute_radar_resonance(self._last_payload)
        prompt = build_radar_card_ai_prompt(
            card_id,
            data,
            resonance_counts=resonance,
        )
        if not prompt:
            page_notify(self._page, "该卡片暂无可解读内容", level="warning")
            return
        self._page.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt=prompt, source_page=f"雷达·{data.title}"),
            )
        )
        if hasattr(self._page, "status_label"):
            self._page.status_label.setText(f"已发送「{data.title}」AI 解读")

    def request_eod_leader_ai(self) -> None:
        if not self._last_payload:
            page_notify(self._page, "请先刷新雷达数据", level="warning")
            return
        prompt = build_eod_leader_prompt(self._last_payload)
        if not prompt:
            page_notify(self._page, "缺少龙头/梯队卡片数据，请先刷新相关卡片", level="warning")
            return
        if self._page.event_engine is None:
            page_notify(self._page, "AI 服务未就绪", level="warning")
            return
        self._page.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt=prompt, source_page="雷达"),
            )
        )
        if hasattr(self._page, "status_label"):
            self._page.status_label.setText("已发送盘后龙头解读请求")

    def request_resonance_ai_summary(self) -> None:
        if not self._last_payload:
            page_notify(self._page, "请先刷新雷达数据", level="warning")
            return
        prompt = build_radar_resonance_ai_prompt(self._last_payload)
        if not prompt:
            page_notify(self._page, "当前无共振标的", level="warning")
            return
        if self._page.event_engine is None:
            page_notify(self._page, "AI 服务未就绪", level="warning")
            return
        self._page.event_engine.put(
            Event(
                EVENT_ASK_AI,
                AskAiRequest(prompt=prompt, source_page="雷达"),
            )
        )
        if hasattr(self._page, "status_label"):
            self._page.status_label.setText("已发送共振 AI 解读请求")

    def _publish_radar_ai_context(self) -> None:
        from vnpy_ashare.ai.context.radar import format_radar_page_extra
        from vnpy_ashare.quotes.radar.radar_board_store import get_radar_board_snapshot

        quote_service = self._page._get_quote_service()
        if quote_service is None:
            return
        item = self._page.current_item
        quote = None
        bar_count = 0
        if item is not None:
            quote = self._page.quote_map.get(item.tickflow_symbol)
            key = (item.symbol, item.exchange)
            meta = self._page.bar_meta.get(key)
            bar_count = meta.count if meta else 0
        snapshot = get_radar_board_snapshot()
        extra = format_radar_page_extra(snapshot)
        quote_service.publish_quote_context(
            page="雷达",
            item=item,
            quote=quote,
            bar_count=bar_count,
            signal_extra=extra,
        )

    def _on_resonance_short_term_focus(self) -> None:
        panel = self._resonance_panel
        if panel is None:
            return
        entries = panel.current_tab_entries()
        if not entries:
            page_notify(self._page, "暂无共振标的", level="warning")
            return
        service = get_watchlist_service(self._page._get_main_engine())
        if service is None:
            page_notify(self._page, "自选服务未就绪", level="warning")
            return
        result = add_short_term_focus(service, resonance_entries_to_rows(entries))
        if not result.group_id:
            page_notify(self._page, "无法创建「短线关注」分组（分组数已满）", level="warning")
            return
        parts = [f"已写入「{result.group_name}」{result.group_added} 只"]
        if result.watchlist_added:
            parts.append(f"新增自选 {result.watchlist_added} 只")
        if result.skipped:
            parts.append(f"跳过 {result.skipped} 只")
        page_notify(self._page, " · ".join(parts))

    def _cancel_card_worker(self, card_id: str) -> None:
        worker = self._card_workers.pop(card_id, None)
        if worker is None:
            return
        worker.request_cancel()
        release_thread(self._retired_workers, worker, timeout_ms=0)

    def _cancel_all_workers(self) -> None:
        card_ids = list(self._card_workers)
        for card_id in card_ids:
            self._cancel_card_worker(card_id)

    def _release_worker(self, worker: RadarCardLoadWorker) -> None:
        card_id = worker.card_id
        if self._card_workers.get(card_id) is worker:
            self._card_workers.pop(card_id, None)
        release_thread(self._retired_workers, worker)

    def _on_card_loaded(self, card_id: str, data: RadarCardData, quote_only: bool = False) -> None:
        if quote_only:
            self._last_payload[card_id] = data
            self._board.apply_quote_update(card_id, data.rows)
            return
        self._auto_refresh_ticks[card_id] = 0
        self._last_payload[card_id] = data
        self._board.apply_card(card_id, data, resonance_counts=self._cached_resonance)
        self._schedule_resonance_sync()

    def _schedule_resonance_sync(self) -> None:
        self._resonance_sync_timer.start(_RADAR_RESONANCE_SYNC_DEBOUNCE_MS)

    def _flush_resonance_sync(self) -> None:
        if not self._last_payload:
            return
        self._cached_resonance = compute_radar_resonance(self._last_payload)
        self._board.sync_resonance(self._cached_resonance)
        self._sync_resonance_panel()
        self._update_status(resonance=self._cached_resonance)

    def _sync_resonance_panel(self) -> None:
        panel = self._resonance_panel
        if panel is None:
            return
        snapshot = build_radar_board_snapshot(self._last_payload)
        set_radar_board_snapshot(snapshot)
        set_radar_resonance_entries(snapshot.resonance_entries)
        statistical = enrich_resonance_entries(
            build_radar_resonance_list(self._last_payload, mode="statistical"),
            self._last_payload,
        )
        predictive = enrich_resonance_entries(
            build_radar_resonance_list(self._last_payload, mode="predictive"),
            self._last_payload,
        )
        panel.apply_entries(
            snapshot.resonance_entries,
            statistical=statistical,
            predictive=predictive,
            allow_new_positions=snapshot.allow_new_positions,
            emotion_stage_label=snapshot.emotion_stage_label,
            row_lookup=row_lookup_from_payload(self._last_payload),
            resonance_count=snapshot.resonance_count,
            dragon_1_count=snapshot.dragon_1_count,
            risk_vt_symbols=collect_radar_risk_vt_symbols(self._last_payload),
        )
        self._publish_radar_ai_context()

    def _on_card_failed(self, card_id: str, message: str) -> None:
        widget = self._board.card(card_id)
        data = self._last_payload.get(card_id)
        if widget is not None:
            if data is not None:
                resonance = compute_radar_resonance(self._last_payload)
                widget.apply_data(data, resonance_counts=resonance)
            else:
                spec = RADAR_CARD_BY_ID.get(card_id)
                widget.apply_data(
                    RadarCardData(
                        card_id=card_id,
                        title=spec.title if spec is not None else card_id,
                        subtitle="",
                        rows=(),
                        empty_message=f"加载失败：{message}",
                        updated_at="",
                    )
                )
        self._schedule_resonance_sync()
        page_notify(self._page, f"卡片加载失败：{message}", level="warning")
        self._update_status()

    def _update_status(self, *, resonance: dict[str, int] | None = None) -> None:
        if not hasattr(self._page, "status_label"):
            return
        active = sum(1 for worker in self._card_workers.values() if thread_is_active(worker))
        if active:
            self._page.status_label.setText(f"雷达加载中…（{active} 张卡）")
            return
        counts = resonance if resonance is not None else compute_radar_resonance(self._last_payload)
        status = "就绪"
        if counts:
            status += f" · 共振 {len(counts)} 只"
        self._page.status_label.setText(status)

    def _on_variant_changed(self, card_id: str, variant_key: str) -> None:
        if not variant_key or card_id not in self._card_variants:
            return
        self._card_variants[card_id] = variant_key
        if card_id == "sector_theme":
            self._sector_variant = variant_key
        elif card_id == "sector_flow_hot":
            pass
        elif card_id == "outlook_scenario":
            pass
        elif card_id == "outlook_predict":
            save_predict_model_mode(variant_key)  # type: ignore[arg-type]
        self.refresh_card(card_id)

    def _on_row_activated(self, vt_symbol: str) -> None:
        if not vt_symbol or vt_symbol.startswith("__stat__:"):
            return
        self._on_stock_analysis(vt_symbol)

    def _on_view_run(self, run_id: str, page_key: str) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_screener_run"):
            page_notify(self._page, "无法打开选股结果页", level="warning")
            return
        host.open_screener_run(run_id, page_key=page_key)

    def _on_sector_flow(self, card_id: str) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_sector_flow"):
            page_notify(self._page, "无法打开板块资金页", level="warning")
            return
        card = self._board.card(card_id)
        sector_ids = card.sector_names() if card is not None else []
        host.open_sector_flow(sector_ids if sector_ids else None)

    def _on_sector_rotation(self, card_id: str) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_sector_flow"):
            page_notify(self._page, "无法打开板块资金页", level="warning")
            return
        card = self._board.card(card_id)
        sector_ids = card.sector_names() if card is not None else []
        host.open_sector_flow(
            sector_ids if sector_ids else None,
            tab="rotation",
            sector_kind="industry",
        )

    def _find_main_window(self) -> QtWidgets.QWidget | None:
        widget: QtWidgets.QWidget | None = self._page
        while widget is not None:
            if hasattr(widget, "open_screener_run") or hasattr(widget, "open_sector_flow") or hasattr(widget, "open_screener_radar_resonance"):
                return widget
            widget = widget.parentWidget()
        return None

    def _on_add_watchlist(self, vt_symbol: str) -> None:
        service = get_watchlist_service(self._page._get_main_engine())
        if service is None:
            page_notify(self._page, "自选服务未就绪", level="warning")
            return
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            page_notify(self._page, f"无法解析合约：{vt_symbol}", level="warning")
            return
        if not service.add(item.symbol, item.exchange, item.name):
            reason = service.add_failure_reason(item.symbol, item.exchange)
            if reason == "full":
                page_notify(self._page, "自选池已满", level="warning")
            else:
                page_notify(self._page, f"已在自选池中：{vt_symbol}")
            return
        page_notify(self._page, f"已加入自选：{item.name or vt_symbol}")

    def _on_batch_add_watchlist(self, card_id: str) -> None:
        service = get_watchlist_service(self._page._get_main_engine())
        if service is None:
            page_notify(self._page, "自选服务未就绪", level="warning")
            return
        data = self._last_payload.get(card_id)
        if data is None or not data.rows:
            page_notify(self._page, "该卡片暂无可加入标的", level="warning")
            return
        added = skipped = 0
        full_hit = False
        for row in data.rows:
            item = parse_stock_symbol(row.vt_symbol)
            if item is None:
                skipped += 1
                continue
            if service.add(item.symbol, item.exchange, row.name or item.name):
                added += 1
            else:
                reason = service.add_failure_reason(item.symbol, item.exchange)
                if reason == "full":
                    full_hit = True
                    break
                skipped += 1
        if full_hit:
            page_notify(self._page, f"自选池已满，已加入 {added} 只", level="warning")
            return
        if added == 0 and skipped:
            page_notify(self._page, f"全部已在自选池中（{skipped} 只）")
            return
        message = f"已加入 {added} 只"
        if skipped:
            message += f"，跳过 {skipped} 只"
        page_notify(self._page, message)

    def _notify_watchlist_pool_result(self, result) -> None:
        if result.watchlist_added == 0:
            if result.skipped:
                page_notify(self._page, "标的已在自选池或无法加入")
            else:
                page_notify(self._page, "暂无可加入自选的标的", level="warning")
            return
        parts = [f"已加入自选 {result.watchlist_added} 只"]
        if result.skipped:
            parts.append(f"跳过 {result.skipped} 只")
        page_notify(self._page, " · ".join(parts))

    def _on_resonance_dragon_watchlist(self) -> None:
        service = get_watchlist_service(self._page._get_main_engine())
        if service is None:
            page_notify(self._page, "自选服务未就绪", level="warning")
            return
        rows = collect_dragon_1_rows(self._last_payload)
        if not rows:
            page_notify(self._page, "暂无龙一标的", level="warning")
            return
        result = add_rows_to_watchlist_pool(service, rows)
        self._notify_watchlist_pool_result(result)

    def _on_resonance_batch_add_watchlist(self) -> None:
        panel = self._resonance_panel
        if panel is None:
            return
        entries = panel.current_tab_entries()
        if not entries:
            page_notify(self._page, "暂无共振标的", level="warning")
            return
        service = get_watchlist_service(self._page._get_main_engine())
        if service is None:
            page_notify(self._page, "自选服务未就绪", level="warning")
            return
        added = skipped = 0
        full_hit = False
        for entry in entries:
            item = parse_stock_symbol(entry.vt_symbol)
            if item is None:
                skipped += 1
                continue
            if service.add(item.symbol, item.exchange, entry.name or item.name):
                added += 1
            else:
                reason = service.add_failure_reason(item.symbol, item.exchange)
                if reason == "full":
                    full_hit = True
                    break
                skipped += 1
        if full_hit:
            page_notify(self._page, f"自选池已满，已加入 {added} 只", level="warning")
            return
        if added == 0 and skipped:
            page_notify(self._page, f"共振标的全部已在自选池中（{skipped} 只）")
            return
        message = f"共振标的已加入 {added} 只"
        if skipped:
            message += f"，跳过 {skipped} 只"
        page_notify(self._page, message)

    def _on_stock_analysis(self, vt_symbol: str) -> None:
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            page_notify(self._page, f"无法解析合约：{vt_symbol}", level="warning")
            return
        row_hint = self._radar_row_hint(vt_symbol)
        show_stock_analysis_from_quotes_page(
            item=item,
            page=self._page,
            row_hint=row_hint,
            parent=self._page,
        )

    def _radar_row_hint(self, vt_symbol: str) -> dict[str, object] | None:
        for data in self._last_payload.values():
            for row in data.rows:
                if row.vt_symbol == vt_symbol:
                    hint: dict[str, object] = {
                        "vt_symbol": row.vt_symbol,
                        "symbol": row.symbol,
                        "name": row.name,
                    }
                    if row.price is not None:
                        hint["last_price"] = row.price
                    if row.change_pct is not None:
                        hint["change_pct"] = row.change_pct
                    return hint
        return None
