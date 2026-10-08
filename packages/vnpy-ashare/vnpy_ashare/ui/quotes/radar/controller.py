"""雷达页控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.app.engine_access import get_watchlist_service
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.radar.loaders import (
    RadarCardData,
    build_eod_leader_prompt,
    build_radar_ai_prompt,
    build_radar_card_ai_prompt,
    build_radar_resonance_ai_prompt,
    compute_radar_resonance,
)
from vnpy_ashare.quotes.radar.loaders.load import RADAR_SNAPSHOT_CARD_IDS
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import OUTLOOK_SIGNAL_CARD_IDS, save_outlook_strategy_class
from vnpy_ashare.quotes.radar.predict.predict_prefs import load_predict_model_mode, save_predict_model_mode
from vnpy_ashare.quotes.radar.radar_board_store import set_radar_board_snapshot
from vnpy_ashare.quotes.radar.radar_card_snapshot_cache import peek_radar_card_snapshot, radar_card_variant_key
from vnpy_ashare.quotes.radar.radar_full_refresh_prefs import load_radar_full_refresh_every, save_radar_full_refresh_every
from vnpy_ashare.quotes.radar.radar_catalog import (
    DEFAULT_LEADER_PICK_VARIANT,
    DEFAULT_SECTOR_VARIANT,
    RadarGroupKey,
    auto_refresh_card_ids,
    list_radar_cards,
    list_radar_cards_for_group,
    list_radar_cards_for_mode,
    list_radar_groups_for_mode,
    radar_card_group,
)
from vnpy_ashare.quotes.radar.radar_horizon import OUTLOOK_FORCE_RECOMPUTE_CARD_IDS
from vnpy_ashare.quotes.radar.radar_market_emotion import is_stat_row
from vnpy_ashare.quotes.radar.radar_models import (
    collect_radar_quote_vt_symbols,
    quotes_for_vt_symbols,
    refresh_radar_card_quotes_from_map,
)
from vnpy_ashare.quotes.radar.radar_resonance_prefs import DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS
from vnpy_ashare.quotes.radar.radar_resonance_store import set_radar_resonance_entries
from vnpy_ashare.services.watchlist_short_term import (
    add_rows_to_watchlist_pool,
    add_short_term_focus,
    collect_dragon_1_rows,
    resonance_entries_to_rows,
)
from vnpy_ashare.trading.plan.propose import _next_trade_date
from vnpy_ashare.ui.features.stock_analysis.open import show_stock_analysis_from_quotes_page
from vnpy_ashare.ui.quotes.page.config import save_radar_card_refresh_ms
from vnpy_ashare.ui.quotes.radar.group_load_plan import (
    RADAR_GROUP_LOAD_MIN_CARDS,
    is_usable_cached_card,
    plan_group_load,
    sort_loaded_cards_for_apply,
)
from vnpy_ashare.ui.quotes.radar.load_pipeline import RadarLoadPipeline
from vnpy_ashare.ui.quotes.radar.payload_view import (
    build_resonance_panel_model,
    failed_card_placeholder,
    format_radar_status_text,
    radar_row_hint_from_payload,
)
from vnpy_ashare.ui.quotes.radar.resonance_weight_dialog import RadarResonanceWeightDialog
from vnpy_ashare.ui.quotes.radar.signal_wiring import BOARD_WIRING, PANEL_WIRING, bind_signals
from vnpy_ashare.ui.quotes.radar.stagger_queue import DebouncedCall, StaggerQueue
from vnpy_ashare.ui.quotes.radar.variant_wiring import build_default_card_variants, card_load_variants
from vnpy_ashare.ui.quotes.radar.watchlist_batch import add_vt_symbols_to_watchlist, format_watchlist_batch_notify
from vnpy_ashare.ui.quotes.radar.worker import RadarCardLoadWorker, RadarGroupLoadWorker
from vnpy_ashare.ui.quotes.radar.worker_host import RadarWorkerHost
from vnpy_ashare.ui.quotes.watchlist_positions.plan_dialog import TradingPlanDialog
from vnpy_ashare.ui.shell.deferred_idle import run_when_idle
from vnpy_common.ui.feedback import page_notify

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage
    from vnpy_ashare.ui.quotes.radar.board import RadarBoard
    from vnpy_ashare.ui.quotes.radar.resonance_panel import RadarResonancePanel

_RADAR_CARD_REFRESH_STAGGER_MS = 80
_RADAR_UI_APPLY_STAGGER_MS = 16
_RADAR_CACHE_APPLY_STAGGER_MS = 8
_RADAR_RESONANCE_SYNC_DEBOUNCE_MS = 120
_RADAR_PREFETCH_NOT_BEFORE_MS = 3000
_RADAR_PREFETCH_NEXT_GROUP_MS = 800


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
        self._workers = RadarWorkerHost()
        self._pipeline = RadarLoadPipeline()
        self._sector_variant = DEFAULT_SECTOR_VARIANT
        self._card_variants: dict[str, str] = build_default_card_variants()
        self._last_payload: dict[str, RadarCardData] = {}
        self._cached_resonance: dict[str, int] = {}
        self._auto_refresh_ticks: dict[str, int] = {}
        self._auto_refresh_timers: dict[str, QtCore.QTimer] = {}
        self._apply_queue: StaggerQueue[tuple[str, RadarCardData]] = StaggerQueue(
            self,
            interval_ms=_RADAR_UI_APPLY_STAGGER_MS,
            on_item=lambda item: self._on_card_loaded(item[0], item[1]),
        )
        self._cache_apply_queue: StaggerQueue[str] = StaggerQueue(
            self,
            interval_ms=_RADAR_CACHE_APPLY_STAGGER_MS,
            on_item=self._apply_cached_card,
        )
        self._refresh_queue: StaggerQueue[tuple[str, dict[str, object]]] = StaggerQueue(
            self,
            interval_ms=_RADAR_CARD_REFRESH_STAGGER_MS,
            on_item=self._apply_refresh_item,
        )
        self._resonance_sync = DebouncedCall(
            self,
            interval_ms=_RADAR_RESONANCE_SYNC_DEBOUNCE_MS,
            callback=self._flush_resonance_sync,
        )
        self._session_timer = QtCore.QTimer(self)
        self._session_timer.setInterval(30_000)
        self._session_timer.timeout.connect(self._on_session_tick)
        self._setup_auto_refresh_timers()

        bind_signals(board, self, BOARD_WIRING)
        if self._resonance_panel is not None:
            bind_signals(self._resonance_panel, self, PANEL_WIRING)

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
        self._workers.cancel_all()
        self._clear_all_card_loading()
        self._pipeline.reset()
        self._refresh_queue.clear()
        self._apply_queue.clear()
        self._cache_apply_queue.clear()
        self._resonance_sync.stop()

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
        self._refresh_live_quotes_for_current_group()
        self._page._update_refresh_hint_label()

    def _refresh_live_quotes_for_current_group(self) -> None:
        """盘中同步刷新当前分组各卡行的现价/涨幅（批量行情查询，避免逐卡阻塞主线程）。"""
        if not is_ashare_trading_session():
            return
        mode = self._board.current_mode()
        group_key = self._board.current_group(mode)
        pending: list[tuple[str, RadarCardData]] = []
        for spec in list_radar_cards_for_group(mode, group_key):
            if not self._card_is_visible(spec.id):
                continue
            data = self._last_payload.get(spec.id)
            if data is None or not data.rows:
                continue
            if all(is_stat_row(row.vt_symbol) for row in data.rows):
                continue
            pending.append((spec.id, data))
        if not pending:
            return
        quotes = quotes_for_vt_symbols(collect_radar_quote_vt_symbols([data for _card_id, data in pending]))
        for card_id, data in pending:
            refreshed = refresh_radar_card_quotes_from_map(data, quotes)
            self._last_payload[card_id] = refreshed
            self._board.apply_quote_update(card_id, refreshed.rows)

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
            if tick % load_radar_full_refresh_every(card_id) != 0:
                self.refresh_card(card_id, force_recompute=False, quote_only=True)
                return
        self.refresh_card(card_id, force_recompute=False)

    def refresh(self) -> None:
        """错峰刷新全部卡片，避免多张卡同时完成时主线程拥堵。"""
        items: list[tuple[str, dict[str, object]]] = [(spec.id, {}) for spec in list_radar_cards()]
        self._enqueue_refresh_many(items)

    def refresh_current_group(self) -> None:
        """刷新当前分区下子 Tab 内的全部卡片。"""
        mode = self._board.current_mode()
        group_key = self._board.current_group(mode)
        items: list[tuple[str, dict[str, object]]] = [(spec.id, {}) for spec in list_radar_cards_for_group(mode, group_key)]
        self._enqueue_refresh_many(items)

    def refresh_current_mode(self) -> None:
        """刷新当前分区内的全部卡片（含各子 Tab）。"""
        items: list[tuple[str, dict[str, object]]] = [(spec.id, {}) for spec in list_radar_cards_for_mode(self._board.current_mode())]
        self._enqueue_refresh_many(items)

    def _enqueue_refresh(self, card_id: str, **kwargs: object) -> None:
        """批量刷新时错峰启动 worker，单卡手动刷新仍走 refresh_card。"""
        self._enqueue_refresh_many([(card_id, dict(kwargs))])

    def _enqueue_refresh_many(self, items: list[tuple[str, dict[str, object]]]) -> None:
        if not items:
            return
        quote_items: list[tuple[str, dict[str, object]]] = []
        load_items: list[tuple[str, dict[str, object]]] = []
        for card_id, kwargs in items:
            if kwargs.get("quote_only"):
                quote_items.append((card_id, kwargs))
            else:
                load_items.append((card_id, kwargs))
        for card_id, kwargs in quote_items:
            self.refresh_card(
                card_id,
                force_recompute=bool(kwargs.get("force_recompute", False)),
                quote_only=True,
            )
        if not load_items:
            return
        if len(load_items) >= RADAR_GROUP_LOAD_MIN_CARDS:
            self._refresh_queue.clear()
            self._start_group_load(load_items)
            return
        self._refresh_queue.upsert_by_key(load_items, key=lambda item: item[0])

    def _apply_refresh_item(self, item: tuple[str, dict[str, object]]) -> None:
        card_id, kwargs = item
        self.refresh_card(
            card_id,
            force_recompute=bool(kwargs.get("force_recompute", False)),
            quote_only=bool(kwargs.get("quote_only", False)),
        )

    def _on_outlook_strategy_changed(self, class_name: str) -> None:
        if not class_name:
            return
        save_outlook_strategy_class(class_name)
        for card_id in OUTLOOK_SIGNAL_CARD_IDS:
            self._enqueue_refresh(card_id, force_recompute=True)

    def _on_board_mode_changed(self, mode: str) -> None:
        self._workers.cancel_prefetch()
        self._pipeline.clear_prefetch()
        self._sync_resonance_tab_from_board(mode)
        self._start_auto_refresh()
        if self._try_apply_current_group_from_cache():
            return
        self.refresh_current_group()

    def _on_board_group_changed(self, mode: str, _group_key: str) -> None:
        if mode != self._board.current_mode():
            return
        self._workers.cancel_prefetch()
        self._pipeline.clear_prefetch()
        self._start_auto_refresh()
        if self._try_apply_current_group_from_cache():
            return
        self.refresh_current_group()

    def _try_apply_current_group_from_cache(self) -> bool:
        """分组内卡片均已加载过时，直接展示缓存，跳过后台重算。"""
        mode = self._board.current_mode()
        group_key = self._board.current_group(mode)
        card_ids = [spec.id for spec in list_radar_cards_for_group(mode, group_key)]
        if not card_ids:
            return False
        if not all(card_id in self._last_payload for card_id in card_ids):
            return False
        self._apply_group_from_cache(card_ids)
        return True

    def _apply_group_from_cache(self, card_ids: list[str]) -> None:
        self._show_cached_cards(card_ids)
        self._schedule_resonance_sync()
        self._update_status()

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
        if self._workers.group_covers_card(card_id):
            return
        if self._workers.card_is_active(card_id):
            return
        existing = self._last_payload.get(card_id)
        if quote_only and (existing is None or not existing.rows):
            quote_only = False
        worker = RadarCardLoadWorker(
            card_id=card_id,
            **self._card_load_variants(),
            force_recompute=force_recompute,
            quote_only=quote_only,
            existing_data=existing if quote_only else None,
            parent=self._page,
        )
        self._workers.start_card(
            worker,
            on_finished=lambda cid, data, qo, w: self._on_card_loaded(cid, data, qo, worker=w),
            on_failed=self._on_card_failed,
        )
        widget = self._board.card(card_id)
        if widget is not None and not quote_only:
            widget.set_loading(True)
        self._update_status()

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

    def _card_load_variants(self) -> dict[str, str]:
        return card_load_variants(self._card_variants)

    # 测试兼容：Worker / 流水线状态直读
    @property
    def _group_worker(self) -> RadarGroupLoadWorker | None:
        return self._workers.group

    @_group_worker.setter
    def _group_worker(self, worker: RadarGroupLoadWorker | None) -> None:
        self._workers.group = worker

    @property
    def _deferred_group_items(self) -> list[tuple[str, dict[str, object]]]:
        return self._pipeline.deferred_viewport

    @_deferred_group_items.setter
    def _deferred_group_items(self, value: list[tuple[str, dict[str, object]]]) -> None:
        self._pipeline.deferred_viewport = value

    @property
    def _deferred_tier_batches(self) -> list[list[tuple[str, dict[str, object]]]]:
        return self._pipeline.deferred_tiers

    @_deferred_tier_batches.setter
    def _deferred_tier_batches(self, value: list[list[tuple[str, dict[str, object]]]]) -> None:
        self._pipeline.deferred_tiers = value

    @property
    def _prefetch_mode(self) -> str | None:
        return self._pipeline.prefetch_mode

    @_prefetch_mode.setter
    def _prefetch_mode(self, value: str | None) -> None:
        self._pipeline.prefetch_mode = value

    @property
    def _prefetch_siblings(self) -> list[str]:
        return self._pipeline.prefetch_siblings

    @_prefetch_siblings.setter
    def _prefetch_siblings(self, value: list[str]) -> None:
        self._pipeline.prefetch_siblings = value

    def _variant_key_for_card(self, card_id: str) -> str:
        return radar_card_variant_key(card_id, self._card_load_variants())

    def _resolve_cached_card(self, card_id: str) -> RadarCardData | None:
        cached = self._last_payload.get(card_id)
        if cached is None and card_id in RADAR_SNAPSHOT_CARD_IDS:
            cached = peek_radar_card_snapshot(card_id, variant_key=self._variant_key_for_card(card_id))
        return cached if is_usable_cached_card(cached) else None

    def _show_cached_cards(self, card_ids: frozenset[str] | set[str] | list[str]) -> None:
        """有缓存时先展示旧数据，后台刷新完成后再覆盖（分帧 apply，避免主线程卡顿）。"""
        queue = [card_id for card_id in card_ids if self._resolve_cached_card(card_id) is not None]
        if not queue:
            return
        self._cache_apply_queue.extend_unique(queue, key=lambda card_id: card_id)

    def _apply_cached_card(self, card_id: str) -> None:
        cached = self._resolve_cached_card(card_id)
        if cached is not None:
            self._last_payload.setdefault(card_id, cached)
            self._board.apply_card(card_id, cached, resonance_counts=self._cached_resonance)

    # 测试兼容：缓存 apply 剩余队列
    @property
    def _pending_cache_apply_queue(self) -> list[str]:
        return self._cache_apply_queue.pending

    def _set_cards_loading(self, card_ids: frozenset[str] | set[str], *, loading: bool) -> None:
        for card_id in card_ids:
            widget = self._board.card(card_id)
            if widget is not None:
                widget.set_loading(loading)

    def _clear_all_card_loading(self) -> None:
        for spec in list_radar_cards():
            widget = self._board.card(spec.id)
            if widget is not None:
                widget.set_loading(False)

    def _start_group_load(
        self,
        items: list[tuple[str, dict[str, object]]],
        *,
        skip_viewport_split: bool = False,
    ) -> None:
        fresh = not skip_viewport_split
        if fresh:
            self._workers.cancel_prefetch()

        plan = plan_group_load(
            items,
            visible_ids=set(self._board.visible_card_ids_for_current_group()),
            skip_viewport_split=skip_viewport_split,
        )
        self._pipeline.apply_plan(plan, fresh=fresh)
        self._run_group_worker(plan.run_now)

    def _run_group_worker(self, items: list[tuple[str, dict[str, object]]]) -> None:
        card_ids = frozenset(card_id for card_id, _kwargs in items)
        self._show_cached_cards(card_ids)
        self._set_cards_loading(card_ids, loading=True)
        self._update_status()

        worker = RadarGroupLoadWorker(
            items=items,
            parent=self._page,
            **self._card_load_variants(),
        )
        self._workers.start_group(
            worker,
            on_finished=lambda loaded, errors, w: self._on_group_loaded(loaded, errors, worker=w),
            on_failed=self._on_group_failed,
            cancel_card_ids=card_ids,
        )

    def _on_group_loaded(
        self,
        loaded: dict[str, RadarCardData],
        errors: dict[str, str],
        *,
        worker: RadarGroupLoadWorker,
    ) -> None:
        if not self._workers.is_current_group(worker):
            return
        visible_ids = set(self._board.visible_card_ids_for_current_group())
        apply_items = sort_loaded_cards_for_apply(loaded, visible_ids)
        for card_id, message in errors.items():
            self._on_card_failed(card_id, message)
        if apply_items:
            self._apply_queue.replace(apply_items)
        else:
            self._update_status()
        continuation = self._pipeline.pop_continuation()
        if continuation is not None:
            self._start_group_load(continuation, skip_viewport_split=True)
            return
        self._schedule_sibling_prefetch()

    def _schedule_sibling_prefetch(self) -> None:
        host = self._find_main_window()
        if host is None:
            return
        mode = self._board.current_mode()
        current = self._board.current_group(mode)
        siblings: list[str] = [group_key for group_key, _label in list_radar_groups_for_mode(mode) if group_key != current]
        if not siblings:
            return
        self._pipeline.arm_prefetch(mode, siblings)

        def _kick() -> None:
            self._drain_prefetch_siblings()

        run_when_idle(host, _kick, not_before_ms=_RADAR_PREFETCH_NOT_BEFORE_MS)

    def _drain_prefetch_siblings(self) -> None:
        if not self._pipeline.has_prefetch:
            return
        if self._workers.group_is_active():
            QtCore.QTimer.singleShot(_RADAR_PREFETCH_NEXT_GROUP_MS, self._drain_prefetch_siblings)
            return
        if self._workers.prefetch_is_active():
            return
        if not self._pipeline.prefetch_still_valid(self._board.current_mode()):
            return
        group_key = self._pipeline.pop_prefetch_sibling()
        if group_key is None or self._pipeline.prefetch_mode is None:
            return
        items: list[tuple[str, dict[str, object]]] = [
            (spec.id, {}) for spec in list_radar_cards_for_group(self._pipeline.prefetch_mode, cast(RadarGroupKey, group_key))
        ]
        if len(items) < RADAR_GROUP_LOAD_MIN_CARDS:
            QtCore.QTimer.singleShot(0, self._drain_prefetch_siblings)
            return
        self._start_prefetch_group(items)

    def _start_prefetch_group(self, items: list[tuple[str, dict[str, object]]]) -> None:
        worker = RadarGroupLoadWorker(
            items=items,
            parent=self._page,
            **self._card_load_variants(),
        )
        self._workers.start_prefetch(
            worker,
            on_finished=lambda loaded, errors, w: self._on_prefetch_loaded(loaded, errors, worker=w),
        )

    def _on_prefetch_loaded(
        self,
        loaded: dict[str, RadarCardData],
        errors: dict[str, str],
        *,
        worker: RadarGroupLoadWorker,
    ) -> None:
        if not self._workers.is_current_prefetch(worker):
            return
        for card_id, data in loaded.items():
            self._last_payload[card_id] = data
        for card_id in errors:
            self._last_payload.pop(card_id, None)
        QtCore.QTimer.singleShot(_RADAR_PREFETCH_NEXT_GROUP_MS, self._drain_prefetch_siblings)

    def _on_group_failed(self, message: str) -> None:
        page_notify(self._page, f"雷达批量加载失败：{message}", level="warning")
        self._update_status()

    def _on_card_loaded(
        self,
        card_id: str,
        data: RadarCardData,
        quote_only: bool = False,
        *,
        worker: RadarCardLoadWorker | None = None,
    ) -> None:
        if not self._workers.is_current_card(card_id, worker):
            return
        if quote_only:
            self._last_payload[card_id] = data
            self._board.apply_quote_update(card_id, data.rows)
            return
        self._auto_refresh_ticks[card_id] = 0
        self._last_payload[card_id] = data
        self._board.apply_card(card_id, data, resonance_counts=self._cached_resonance)
        self._schedule_resonance_sync()

    def _schedule_resonance_sync(self) -> None:
        self._resonance_sync.schedule()

    def _flush_resonance_sync(self) -> None:
        if not self._last_payload:
            return
        self._cached_resonance = compute_radar_resonance(self._last_payload)
        self._board.sync_resonance(self._cached_resonance)
        self._update_status(resonance=self._cached_resonance)
        # 侧栏共振列表重建较重，延后一帧避免与多张卡片 apply_card 挤在同一事件循环。
        QtCore.QTimer.singleShot(0, self._sync_resonance_panel)

    def _sync_resonance_panel(self) -> None:
        panel = self._resonance_panel
        if panel is None:
            return
        model = build_resonance_panel_model(self._last_payload)
        snapshot = model.snapshot
        set_radar_board_snapshot(snapshot)
        set_radar_resonance_entries(snapshot.resonance_entries)
        panel.apply_entries(
            snapshot.resonance_entries,
            statistical=model.statistical,
            predictive=model.predictive,
            allow_new_positions=snapshot.allow_new_positions,
            emotion_stage_label=snapshot.emotion_stage_label,
            row_lookup=model.row_lookup,
            resonance_count=snapshot.resonance_count,
            dragon_1_count=snapshot.dragon_1_count,
            risk_vt_symbols=model.risk_vt_symbols,
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
                widget.apply_data(failed_card_placeholder(card_id, message))
        self._schedule_resonance_sync()
        page_notify(self._page, f"卡片加载失败：{message}", level="warning")
        self._update_status()

    def _update_status(self, *, resonance: dict[str, int] | None = None) -> None:
        if not hasattr(self._page, "status_label"):
            return
        self._page.status_label.setText(
            format_radar_status_text(
                active_workers=self._workers.active_load_count(),
                payload=self._last_payload,
                resonance=resonance,
            )
        )

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
        result = add_vt_symbols_to_watchlist(
            service,
            ((row.vt_symbol, row.name or "") for row in data.rows),
        )
        notify = format_watchlist_batch_notify(result)
        page_notify(self._page, notify.message, level=notify.level)

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
        result = add_vt_symbols_to_watchlist(
            service,
            ((entry.vt_symbol, entry.name or "") for entry in entries),
        )
        notify = format_watchlist_batch_notify(
            result,
            all_skipped_message="共振标的全部已在自选池中",
            success_prefix="共振标的已加入",
        )
        page_notify(self._page, notify.message, level=notify.level)

    def _on_stock_analysis(self, vt_symbol: str) -> None:
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            page_notify(self._page, f"无法解析合约：{vt_symbol}", level="warning")
            return
        row_hint = radar_row_hint_from_payload(self._last_payload, vt_symbol)
        show_stock_analysis_from_quotes_page(
            item=item,
            page=self._page,
            row_hint=row_hint,
            parent=self._page,
        )
