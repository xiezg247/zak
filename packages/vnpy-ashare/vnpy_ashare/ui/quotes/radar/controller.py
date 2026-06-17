"""雷达页控制器。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy.event import Event
from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_ashare.app.engine_access import get_watchlist_service
from vnpy_ashare.app.events import EVENT_ASK_AI, AskAiRequest
from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.radar.predict.predict_prefs import load_predict_model_mode, save_predict_model_mode
from vnpy_ashare.quotes.radar.radar_catalog import (
    DEFAULT_LEADER_PICK_VARIANT,
    DEFAULT_LIMIT_LADDER_VARIANT,
    DEFAULT_SCENARIO_VARIANT,
    DEFAULT_SCREEN_TASK_VARIANT,
    DEFAULT_SECTOR_VARIANT,
    RADAR_CARD_BY_ID,
    auto_refresh_card_ids,
    full_refresh_every_n_ticks,
    list_radar_cards,
    list_radar_cards_for_mode,
)
from vnpy_ashare.quotes.radar.radar_full_refresh_prefs import save_radar_full_refresh_every
from vnpy_ashare.quotes.radar.radar_horizon import OUTLOOK_FORCE_RECOMPUTE_CARD_IDS
from vnpy_ashare.quotes.radar.radar_loaders import (
    RadarCardData,
    build_radar_ai_prompt,
    build_radar_card_ai_prompt,
    build_radar_resonance_ai_prompt,
    build_radar_resonance_list,
    compute_radar_resonance,
)
from vnpy_ashare.quotes.radar.radar_resonance_prefs import DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS
from vnpy_ashare.quotes.radar.radar_resonance_store import set_radar_resonance_entries
from vnpy_ashare.services.watchlist_short_term import (
    SHORT_TERM_OBSERVATION_GROUP_NAME,
    add_rows_to_short_term_observation_group,
    collect_dragon_1_rows,
)
from vnpy_ashare.ui.features.stock_analysis import show_stock_analysis_from_quotes_page
from vnpy_ashare.ui.quotes.page.config import save_radar_card_refresh_ms
from vnpy_ashare.ui.quotes.radar.resonance_weight_dialog import RadarResonanceWeightDialog
from vnpy_ashare.ui.quotes.radar.worker import RadarCardLoadWorker
from vnpy_common.ui.feedback import page_notify
from vnpy_common.ui.qt_helpers import release_thread, thread_is_active

if TYPE_CHECKING:
    from vnpy_ashare.ui.quotes.page.quotes_page import QuotesPage
    from vnpy_ashare.ui.quotes.radar.card import RadarBoard
    from vnpy_ashare.ui.quotes.radar.resonance_panel import RadarResonancePanel


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
        self._screen_task_variant = DEFAULT_SCREEN_TASK_VARIANT
        self._sector_variant = DEFAULT_SECTOR_VARIANT
        self._card_variants: dict[str, str] = {
            "screen_task": DEFAULT_SCREEN_TASK_VARIANT,
            "sector_theme": DEFAULT_SECTOR_VARIANT,
            "leader_pick": DEFAULT_LEADER_PICK_VARIANT,
            "discovery_limit_ladder": DEFAULT_LIMIT_LADDER_VARIANT,
            "outlook_scenario": DEFAULT_SCENARIO_VARIANT,
            "outlook_predict": load_predict_model_mode(),
        }
        self._last_payload: dict[str, RadarCardData] = {}
        self._auto_refresh_ticks: dict[str, int] = {}
        self._auto_refresh_timers: dict[str, QtCore.QTimer] = {}
        self._session_timer = QtCore.QTimer(self)
        self._session_timer.setInterval(30_000)
        self._session_timer.timeout.connect(self._on_session_tick)
        self._setup_auto_refresh_timers()

        board.variant_changed.connect(self._on_variant_changed)
        board.row_activated.connect(self._on_row_activated)
        board.add_watchlist_requested.connect(self._on_add_watchlist)
        board.batch_add_watchlist_requested.connect(self._on_batch_add_watchlist)
        board.add_observation_group_requested.connect(self._on_add_observation_group)
        board.stock_analysis_requested.connect(self._on_stock_analysis)
        board.view_run_requested.connect(self._on_view_run)
        board.sector_flow_requested.connect(self._on_sector_flow)
        board.refresh_requested.connect(self._on_card_refresh_requested)
        board.quote_refresh_requested.connect(self._on_card_quote_refresh_requested)
        board.ai_requested.connect(self.request_card_ai)
        board.auto_refresh_changed.connect(self._on_auto_refresh_changed)
        board.full_refresh_interval_changed.connect(self._on_full_refresh_interval_changed)
        board.mode_changed.connect(self._on_board_mode_changed)

        panel = self._resonance_panel
        if panel is not None:
            panel.row_activated.connect(self._on_row_activated)
            panel.add_watchlist_requested.connect(self._on_add_watchlist)
            panel.batch_add_watchlist_requested.connect(self._on_resonance_batch_add_watchlist)
            panel.add_dragon_observation_group_requested.connect(self._on_resonance_dragon_observation_group)
            panel.stock_analysis_requested.connect(self._on_stock_analysis)
            panel.ai_resonance_requested.connect(self.request_resonance_ai_summary)
            panel.open_screener_requested.connect(self._on_open_screener_resonance)
            panel.open_leader_screener_requested.connect(self._on_open_screener_leader)
            panel.resonance_weights_requested.connect(self._on_resonance_weights_requested)

    def _on_open_screener_resonance(self) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_screener_radar_resonance"):
            page_notify(self._page, "无法打开选股页", level="warning")
            return
        host.open_screener_radar_resonance()

    def _on_open_screener_leader(self) -> None:
        host = self._find_main_window()
        if host is None or not hasattr(host, "open_screener_leader_screen"):
            page_notify(self._page, "无法打开选股页", level="warning")
            return
        variant = self._card_variants.get("leader_pick", DEFAULT_LEADER_PICK_VARIANT)
        host.open_screener_leader_screen(variant=variant)

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
            self.refresh_card(card_id, force_recompute=True)

    def activate(self) -> None:
        predict_mode = load_predict_model_mode()
        self._card_variants["outlook_predict"] = predict_mode
        predict_card = self._board.card("outlook_predict")
        if predict_card is not None:
            predict_card.set_variant_key(predict_mode)
        self._board.update_tab_badges()
        self._sync_resonance_tab_from_board()
        self._page._refresh_emotion_cycle_chip()
        self.refresh()
        self._start_auto_refresh()
        self._session_timer.start()

    def deactivate(self) -> None:
        self._session_timer.stop()
        self._stop_auto_refresh()
        self._cancel_all_workers()

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

    def _apply_card_auto_refresh(self, card_id: str) -> None:
        timer = self._auto_refresh_timers.get(card_id)
        widget = self._board.card(card_id)
        if timer is None or widget is None:
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
        """并行刷新全部卡片。"""
        for spec in list_radar_cards():
            self.refresh_card(spec.id)

    def refresh_current_mode(self) -> None:
        """刷新当前主区 Tab 内的全部卡片。"""
        for spec in list_radar_cards_for_mode(self._board.current_mode()):
            self.refresh_card(spec.id)

    def _on_board_mode_changed(self, mode: str) -> None:
        self._sync_resonance_tab_from_board(mode)

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
            screen_task_variant=self._card_variants.get("screen_task", DEFAULT_SCREEN_TASK_VARIANT),
            sector_variant=self._card_variants.get("sector_theme", DEFAULT_SECTOR_VARIANT),
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
            self._sync_resonance_panel()
            return
        self._auto_refresh_ticks[card_id] = 0
        self._last_payload[card_id] = data
        resonance = compute_radar_resonance(self._last_payload)
        self._board.apply_card(card_id, data, resonance_counts=resonance)
        self._board.sync_resonance(resonance)
        self._sync_resonance_panel()
        self._update_status(resonance=resonance)

    def _sync_resonance_panel(self) -> None:
        panel = self._resonance_panel
        if panel is None:
            return
        entries = build_radar_resonance_list(self._last_payload)
        statistical = build_radar_resonance_list(self._last_payload, mode="statistical")
        predictive = build_radar_resonance_list(self._last_payload, mode="predictive")
        set_radar_resonance_entries(entries)
        panel.apply_entries(entries, statistical=statistical, predictive=predictive)

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
        self._sync_resonance_panel()
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
        if card_id == "screen_task":
            self._screen_task_variant = variant_key
        elif card_id == "sector_theme":
            self._sector_variant = variant_key
        elif card_id == "outlook_scenario":
            pass
        elif card_id == "outlook_predict":
            save_predict_model_mode(variant_key)  # type: ignore[arg-type]
        self.refresh_card(card_id)

    def _on_row_activated(self, vt_symbol: str) -> None:
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

    def _notify_observation_group_result(self, result) -> None:
        if result.group_added == 0 and result.watchlist_added == 0:
            if result.skipped:
                page_notify(self._page, f"标的已在「{SHORT_TERM_OBSERVATION_GROUP_NAME}」或无法加入")
            else:
                page_notify(self._page, "暂无可加入观察组的标的", level="warning")
            return
        parts = [f"已写入「{SHORT_TERM_OBSERVATION_GROUP_NAME}」{result.group_added} 只"]
        if result.watchlist_added:
            parts.append(f"新入自选 {result.watchlist_added} 只")
        if result.group_created:
            parts.append("已创建分组")
        if result.skipped:
            parts.append(f"跳过 {result.skipped} 只")
        page_notify(self._page, " · ".join(parts))

    def _on_add_observation_group(self, card_id: str) -> None:
        service = get_watchlist_service(self._page._get_main_engine())
        if service is None:
            page_notify(self._page, "自选服务未就绪", level="warning")
            return
        data = self._last_payload.get(card_id)
        if data is None or not data.rows:
            page_notify(self._page, "该卡片暂无可加入标的", level="warning")
            return
        result = add_rows_to_short_term_observation_group(service, data.rows)
        self._notify_observation_group_result(result)

    def _on_resonance_dragon_observation_group(self) -> None:
        service = get_watchlist_service(self._page._get_main_engine())
        if service is None:
            page_notify(self._page, "自选服务未就绪", level="warning")
            return
        rows = collect_dragon_1_rows(self._last_payload)
        if not rows:
            page_notify(self._page, "暂无龙一标的", level="warning")
            return
        result = add_rows_to_short_term_observation_group(service, rows)
        self._notify_observation_group_result(result)

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
