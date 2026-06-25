"""策略信号计算、批量快照与相对指数超额。"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, cast

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from strategies.registry import get_strategy_meta
from strategies.signals import (
    SUPPORTED_SIGNAL_STRATEGIES,
    build_signal_payload_for_strategy,
    list_supported_signal_strategies,
    summarize_double_ma_state,
    summarize_short_breakout_state,
    summarize_swing_ma_state,
    summarize_trend_ma_state,
)
from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.config.preferences.watchlist_signal import SIGNAL_LOOKBACK_BARS
from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.data.pattern_bars import load_daily_bars_batch, load_daily_bars_tail, pattern_load_max_workers
from vnpy_ashare.domain.trading.signal_benchmark import compute_relative_index_excess, resolve_benchmark_return_pct
from vnpy_ashare.domain.trading.signal_snapshot import (
    SIGNAL_BENCHMARK_LOOKBACK,
    SignalSnapshot,
)
from vnpy_ashare.services.analysis_detail.technical.base import _TechnicalAnalyzerBase

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine


class TechnicalSignalsMixin(_TechnicalAnalyzerBase):
    _engine: AshareEngine
    _benchmark_return_cache_key: int | None
    _benchmark_return_cache_val: float | None

    def strategy_signals(
        self,
        symbol: str,
        *,
        class_name: str = "AshareDoubleMaStrategy",
        lookback: int = SIGNAL_LOOKBACK_BARS,
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
    ) -> dict[str, Any]:
        """基于本地 K 线计算策略规则信号（与回测策略逻辑一致）。"""
        item = parse_stock_symbol(symbol)
        if item is None:
            return {"error": f"无法解析代码: {symbol}"}

        meta = get_strategy_meta(class_name)
        if class_name not in SUPPORTED_SIGNAL_STRATEGIES:
            return {
                "error": f"暂不支持策略 {class_name} 的信号计算",
                "supported": list_supported_signal_strategies(),
            }

        lookback = max(30, min(int(lookback or SIGNAL_LOOKBACK_BARS), 250))
        fast_window = max(2, int(fast_window or 10))
        slow_window = max(fast_window + 1, int(slow_window or 20))

        bars = self._load_strategy_bars(item.symbol, item.exchange, scope=scope or "daily", lookback=lookback)
        warnings: list[str] = []
        if len(bars) < slow_window + 5:
            return {
                "symbol": item.vt_symbol,
                "name": item.name,
                "strategy": class_name,
                "strategy_title": meta.title if meta else class_name,
                "warnings": ["本地 K 线不足，请先在数据管理页下载日 K"],
                "sources": ["bar"],
                "supported": list_supported_signal_strategies(),
            }

        tail = bars[-lookback:] if len(bars) >= lookback else bars
        closes = [bar.close_price for bar in tail]
        highs = [bar.high_price for bar in tail]
        volumes = [float(bar.volume) for bar in tail]
        dates: list[date | datetime] = [bar.datetime for bar in tail]

        kind = SUPPORTED_SIGNAL_STRATEGIES[class_name]
        if kind == "double_ma":
            state = summarize_double_ma_state(
                closes,
                dates,
                fast_window=fast_window,
                slow_window=slow_window,
            )
        elif kind == "short_breakout":
            state = summarize_short_breakout_state(
                closes,
                highs,
                dates,
                volumes,
                fast_window=fast_window,
                slow_window=slow_window,
            )
        elif kind == "swing_ma":
            state = summarize_swing_ma_state(
                closes,
                dates,
                volumes,
                lows=[bar.low_price for bar in tail],
                fast_window=fast_window,
                slow_window=slow_window,
            )
        elif kind == "trend_ma":
            state = summarize_trend_ma_state(
                closes,
                dates,
                highs,
                [bar.low_price for bar in tail],
                fast_window=fast_window,
                slow_window=slow_window,
            )
        else:
            return {"error": f"未实现策略信号: {class_name}"}

        if state.get("error"):
            warnings.append(str(state["error"]))

        result: dict[str, Any] = {
            "symbol": item.vt_symbol,
            "name": item.name,
            "strategy": class_name,
            "strategy_title": meta.title if meta else class_name,
            "strategy_summary": meta.summary if meta else "",
            "scope": scope or "daily",
            "bars_used": len(tail),
            "as_of": state.get("as_of"),
            "params": state.get("params"),
            "current": state.get("current"),
            "last_cross": state.get("last_cross"),
            "warnings": warnings,
            "sources": ["bar"],
        }
        if kind == "double_ma":
            result["recent_signals"] = state.get("recent_signals", [])
            result["signal_count"] = state.get("signal_count", 0)
        elif kind == "short_breakout":
            result["last_breakout"] = state.get("last_breakout")
            result["recent_breakouts"] = state.get("recent_breakouts", [])
            result["breakout_count"] = state.get("breakout_count", 0)
        elif kind == "swing_ma":
            result["last_entry"] = state.get("last_entry")
            result["recent_entries"] = state.get("recent_entries", [])
            result["entry_count"] = state.get("entry_count", 0)
            result["recent_signals"] = state.get("recent_signals", [])
            result["signal_count"] = state.get("signal_count", 0)
        elif kind == "trend_ma":
            result["recent_signals"] = state.get("recent_signals", [])
            result["signal_count"] = state.get("signal_count", 0)
            result["adx"] = (state.get("current") or {}).get("adx")
        return result

    def signal_snapshot(
        self,
        symbol: str,
        *,
        class_name: str = "AshareDoubleMaStrategy",
        lookback: int = SIGNAL_LOOKBACK_BARS,
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
    ) -> SignalSnapshot | None:
        """单标的策略信号快照（供自选页表格）。"""
        payload = self._build_signal_payload(
            symbol,
            class_name=class_name,
            lookback=lookback,
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
        )
        if payload is None:
            return None
        return self._payload_to_signal_snapshot(payload)

    def batch_strategy_signals(
        self,
        symbols: list[str],
        *,
        class_name: str = "AshareDoubleMaStrategy",
        lookback: int = SIGNAL_LOOKBACK_BARS,
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
        max_workers: int | None = None,
    ) -> dict[str, SignalSnapshot]:
        """批量计算策略信号（自选池 Worker 调用）。"""
        if not symbols:
            return {}

        self.reset_benchmark_cache()
        lookback = max(30, min(int(lookback or SIGNAL_LOOKBACK_BARS), 250))
        payload_kwargs: dict[str, Any] = {
            "class_name": class_name,
            "lookback": lookback,
            "fast_window": fast_window,
            "slow_window": slow_window,
            "scope": scope,
        }

        bars_by_key: dict[tuple[str, Exchange], list[BarData]] = {}
        if (scope or "daily") == "daily":
            items = []
            for symbol in symbols:
                item = parse_stock_symbol(symbol)
                if item is not None:
                    items.append(item)
            if items:
                bar_workers = pattern_load_max_workers(item_count=len(items)) if max_workers is None else max(1, min(int(max_workers), len(items)))
                bars_by_key = load_daily_bars_batch(
                    items,
                    lookback_bars=lookback,
                    max_workers=bar_workers,
                )

        def worker(symbol: str) -> tuple[str, SignalSnapshot] | None:
            try:
                item = parse_stock_symbol(symbol)
                preloaded = bars_by_key.get((item.symbol, item.exchange)) if item is not None else None
                payload = self._build_signal_payload(
                    symbol,
                    bars=preloaded,
                    **payload_kwargs,
                )
            except Exception:
                return None
            if payload is None:
                return None
            return payload["vt_symbol"], self._payload_to_signal_snapshot(payload)

        if max_workers is None:
            workers = pattern_load_max_workers(item_count=len(symbols))
        else:
            workers = max(1, min(int(max_workers), len(symbols)))

        if workers <= 1:
            results: dict[str, SignalSnapshot] = {}
            for symbol in symbols:
                item = worker(symbol)
                if item is None:
                    continue
                vt_symbol, snapshot = item
                results[vt_symbol] = snapshot
            return results

        pairs = run_parallel_map(symbols, worker, max_workers=workers)
        results = {}
        for item in pairs:
            if item is None:
                continue
            vt_symbol, snapshot = item
            results[vt_symbol] = snapshot
        return results

    def _benchmark_return_pct(self, lookback: int = SIGNAL_BENCHMARK_LOOKBACK) -> float | None:
        if self._benchmark_return_cache_key == lookback:
            return self._benchmark_return_cache_val
        value = resolve_benchmark_return_pct(self._engine.bar_service, lookback=lookback)
        self._benchmark_return_cache_key = lookback
        self._benchmark_return_cache_val = value
        return value

    def _relative_index_excess(
        self,
        symbol: str,
        exchange: Any,
        *,
        lookback: int = SIGNAL_BENCHMARK_LOOKBACK,
    ) -> float | None:
        bench_pct = self._benchmark_return_pct(lookback)
        return compute_relative_index_excess(
            self._engine.bar_service,
            symbol,
            exchange,
            lookback=lookback,
            benchmark_pct=bench_pct,
        )

    def enrich_relative_index(self, snapshot: SignalSnapshot) -> SignalSnapshot:
        """旧快照缺 relative_index_pct 时补算（不改动其它字段）。"""
        if snapshot.relative_index_pct is not None or snapshot.signal == "na":
            return snapshot
        item = parse_stock_symbol(snapshot.vt_symbol)
        if item is None:
            return snapshot
        excess = self._relative_index_excess(item.symbol, item.exchange)
        if excess is None:
            return snapshot

        return snapshot.model_copy(update={"relative_index_pct": excess})

    def enrich_relative_index_batch(
        self,
        snapshots: dict[str, SignalSnapshot],
    ) -> dict[str, SignalSnapshot]:
        if not snapshots:
            return snapshots
        self.reset_benchmark_cache()
        enriched: dict[str, SignalSnapshot] = {}
        for vt_symbol, snapshot in snapshots.items():
            enriched[vt_symbol] = self.enrich_relative_index(snapshot)
        return enriched

    def _load_strategy_bars(
        self,
        symbol: str,
        exchange: Exchange,
        *,
        scope: str,
        lookback: int,
    ) -> list[BarData]:
        """策略信号仅需尾部 K 线，避免从 1990 全量扫库。"""
        if (scope or "daily") == "daily":
            return load_daily_bars_tail(symbol, exchange, lookback_bars=lookback)
        return self._engine.bar_service.load_bars(symbol, exchange, scope or "daily")

    def _build_signal_payload(
        self,
        symbol: str,
        *,
        class_name: str,
        lookback: int,
        fast_window: int,
        slow_window: int,
        scope: str,
        bars: list[BarData] | None = None,
    ) -> dict[str, Any] | None:
        item = parse_stock_symbol(symbol)
        if item is None:
            return None
        if class_name not in SUPPORTED_SIGNAL_STRATEGIES:
            return None

        lookback = max(30, min(int(lookback or SIGNAL_LOOKBACK_BARS), 250))
        fast_window = max(2, int(fast_window or 10))
        slow_window = max(fast_window + 1, int(slow_window or 20))

        if bars is None:
            bars = self._load_strategy_bars(
                item.symbol,
                item.exchange,
                scope=scope or "daily",
                lookback=lookback,
            )
        if len(bars) < slow_window + 5:
            return {
                "vt_symbol": item.vt_symbol,
                "strategy_id": class_name,
                "as_of": "",
                "signal": "na",
                "signal_label": "—",
                "signal_date": None,
                "ref_buy_price": None,
                "ref_sell_price": None,
                "action_ref_buy_price": None,
                "action_ref_sell_price": None,
                "strength": None,
                "reason_summary": "",
                "reasons": (),
                "warnings": ("本地 K 线不足，请先在数据管理页下载日 K",),
            }

        tail = bars[-lookback:] if len(bars) >= lookback else bars
        closes = [bar.close_price for bar in tail]
        highs = [bar.high_price for bar in tail]
        lows = [bar.low_price for bar in tail]
        volumes = [float(bar.volume) for bar in tail]
        dates: list[date | datetime] = [bar.datetime for bar in tail]

        if SUPPORTED_SIGNAL_STRATEGIES.get(class_name) is None:
            return None

        relative_index_pct = self._relative_index_excess(
            item.symbol,
            item.exchange,
        )
        payload = build_signal_payload_for_strategy(
            class_name,
            closes,
            dates,
            vt_symbol=item.vt_symbol,
            fast_window=fast_window,
            slow_window=slow_window,
            highs=highs,
            lows=lows,
            volumes=volumes,
            relative_index_pct=relative_index_pct,
        )
        if payload is None:
            return None
        payload["relative_index_pct"] = relative_index_pct
        return cast(dict[str, Any], payload)

    @staticmethod
    def _payload_to_signal_snapshot(payload: dict[str, Any]) -> SignalSnapshot:
        return SignalSnapshot(
            vt_symbol=str(payload.get("vt_symbol") or ""),
            strategy_id=str(payload.get("strategy_id") or ""),
            as_of=str(payload.get("as_of") or ""),
            signal=payload.get("signal") or "na",
            signal_label=str(payload.get("signal_label") or "—"),
            signal_date=payload.get("signal_date"),
            ref_buy_price=payload.get("ref_buy_price"),
            ref_sell_price=payload.get("ref_sell_price"),
            strength=payload.get("strength"),
            reason_summary=str(payload.get("reason_summary") or ""),
            reasons=tuple(payload.get("reasons") or ()),
            warnings=tuple(payload.get("warnings") or ()),
            last_close=payload.get("last_close"),
            action_ref_buy_price=payload.get("action_ref_buy_price"),
            action_ref_sell_price=payload.get("action_ref_sell_price"),
            fast_ma=payload.get("fast_ma"),
            slow_ma=payload.get("slow_ma"),
            volume_ratio_5d=payload.get("volume_ratio_5d"),
            ma_gap_pct=payload.get("ma_gap_pct"),
            strength_cross=payload.get("strength_cross"),
            strength_alignment=payload.get("strength_alignment"),
            strength_volume=payload.get("strength_volume"),
            strength_pattern=payload.get("strength_pattern"),
            relative_index_pct=payload.get("relative_index_pct"),
        )
