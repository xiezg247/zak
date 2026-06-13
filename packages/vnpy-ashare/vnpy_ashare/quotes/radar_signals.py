"""雷达页策略信号计算与跃迁检测（Worker 线程可用）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from strategies.signals import build_signal_payload_for_strategy
from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig, load_watchlist_signal_config
from vnpy_ashare.data.bar_access import load_scope_bars
from vnpy_ashare.domain.signal_snapshot import SignalKind, SignalSnapshot, signal_missing_kline
from vnpy_ashare.domain.symbols import parse_stock_symbol


def payload_to_snapshot(payload: dict[str, Any]) -> SignalSnapshot:
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


def build_signal_snapshot(
    vt_symbol: str,
    *,
    config: WatchlistSignalConfig | None = None,
) -> SignalSnapshot | None:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return None
    cfg = (config or load_watchlist_signal_config()).normalized()
    slow_window = cfg.slow_window
    bars = load_scope_bars(
        item.symbol,
        item.exchange,
        "daily",
        datetime(1990, 1, 1),
        datetime.now(),
    )
    if len(bars) < slow_window + 5:
        return payload_to_snapshot(
            {
                "vt_symbol": item.vt_symbol,
                "strategy_id": cfg.class_name,
                "as_of": "",
                "signal": "na",
                "signal_label": "—",
                "warnings": ("本地 K 线不足",),
            }
        )

    lookback = min(120, len(bars))
    tail = bars[-lookback:]
    payload = build_signal_payload_for_strategy(
        cfg.class_name,
        [bar.close_price for bar in tail],
        [bar.datetime for bar in tail],
        vt_symbol=item.vt_symbol,
        fast_window=cfg.fast_window,
        slow_window=cfg.slow_window,
        highs=[bar.high_price for bar in tail],
        lows=[bar.low_price for bar in tail],
        volumes=[float(bar.volume) for bar in tail],
    )
    if payload is None:
        return None
    return payload_to_snapshot(payload)


def load_cached_signals(vt_symbols: list[str], *, config: WatchlistSignalConfig | None = None) -> dict[str, SignalSnapshot]:
    from vnpy_ashare.ui.quotes.watchlist_signals.cache import WatchlistSignalDiskCache

    cfg = (config or load_watchlist_signal_config()).normalized()
    cache = WatchlistSignalDiskCache()
    loaded: dict[str, SignalSnapshot] = {}
    for vt_symbol in vt_symbols:
        snap = cache.get_latest(vt_symbol, cfg.cache_key())
        if snap is not None:
            loaded[vt_symbol] = snap
    return loaded


_TRACKED: frozenset[SignalKind] = frozenset({"buy", "sell", "hold"})


def transition_label(before: SignalSnapshot | None, after: SignalSnapshot | None) -> str | None:
    """返回可读跃迁文案，无跃迁则 None。"""
    if before is None or after is None or signal_missing_kline(after):
        return None
    if before.signal == after.signal:
        return None
    if after.signal not in _TRACKED:
        return None
    if before.signal not in _TRACKED and after.signal == "hold":
        return None
    return f"{before.signal_label}→{after.signal_label}"


def compute_signal_transitions(
    vt_symbols: list[str],
    *,
    config: WatchlistSignalConfig | None = None,
    max_compute: int = 20,
) -> dict[str, str]:
    """对比磁盘缓存与现算信号，返回 vt_symbol → 跃迁文案。"""
    if not vt_symbols:
        return {}
    cfg = (config or load_watchlist_signal_config()).normalized()
    cached = load_cached_signals(vt_symbols, config=cfg)
    transitions: dict[str, str] = {}
    for vt_symbol in vt_symbols[: max(1, int(max_compute))]:
        after = build_signal_snapshot(vt_symbol, config=cfg)
        if after is None or signal_missing_kline(after):
            continue
        label = transition_label(cached.get(vt_symbol), after)
        if label:
            transitions[vt_symbol] = label
    return transitions
