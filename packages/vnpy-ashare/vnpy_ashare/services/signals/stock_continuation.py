"""自选信号区：个股延续与统计展望（价量 + 资金 + 板块环境）。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from vnpy.trader.engine import MainEngine

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.app.engine_access import get_sector_flow_service
from vnpy_ashare.data.download_concurrency import continuation_batch_max_workers, run_parallel_map
from vnpy_ashare.domain.market.flow_pattern import classify_flow_pattern_values
from vnpy_ashare.domain.market.sector_flow import SectorFlowOutlookDay, SectorFlowOutlookRow
from vnpy_ashare.domain.symbols.stock import lookup_by_vt_symbol
from vnpy_ashare.domain.time.trade_dates import iter_forward_trade_date_strs
from vnpy_ashare.domain.trading.signal_snapshot import (
    SIGNAL_RECENT_DAYS,
    SignalKind,
    SignalSnapshot,
    signal_age_days,
    signal_expired,
    signal_is_fresh,
    signal_missing_kline,
)
from vnpy_ashare.domain.trading.stock_continuation import (
    STOCK_CONTINUATION_DISCLAIMER,
    STOCK_OUTLOOK_HORIZON_DAYS,
    StockContinuationSnapshot,
    format_bias_compact,
    format_outlook_compact,
)
from vnpy_ashare.screener.data.screening_context import get_stock_industry_map
from vnpy_ashare.services.signals.stock_moneyflow_series import load_stock_moneyflow_values

_PATTERN_BIAS_SEQUENCE: dict[str, tuple[str, str, str]] = {
    "持续流入": ("偏多", "偏多", "震荡"),
    "持续流出": ("偏空", "偏空", "震荡"),
    "先出后入": ("震荡", "偏多", "偏多"),
    "先入后出": ("偏多", "震荡", "偏空"),
    "震荡": ("震荡", "震荡", "震荡"),
}

_PATTERN_BASE_STRENGTH: dict[str, float] = {
    "持续流入": 0.72,
    "持续流出": 0.72,
    "先出后入": 0.58,
    "先入后出": 0.58,
    "震荡": 0.42,
}

_BULLISH_FLOW = frozenset({"持续流入", "先出后入"})
_BEARISH_FLOW = frozenset({"持续流出", "先入后出"})

_HORIZON_DECAY = (1.0, 0.72, 0.50)
_STRENGTH_NEUTRAL_THRESHOLD = 0.35


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _signal_streak_days(snapshot: SignalSnapshot) -> int:
    if snapshot.signal not in ("buy", "sell", "hold"):
        return 0
    age = signal_age_days(snapshot)
    if age is None:
        return 0
    return max(0, age) + 1


def _classify_price_pattern(snapshot: SignalSnapshot) -> str:
    if snapshot.signal == "na" or signal_missing_kline(snapshot):
        return "—"

    age = signal_age_days(snapshot)
    fresh = snapshot.signal in ("buy", "sell") and signal_is_fresh(snapshot)
    expired = snapshot.signal in ("buy", "sell") and signal_expired(snapshot)
    gap = snapshot.ma_gap_pct
    volume = snapshot.volume_ratio_5d
    relative = snapshot.relative_index_pct

    if snapshot.signal == "buy":
        bullish_gap = gap is not None and gap > 0
        strong_volume = volume is not None and volume >= 1.2
        weak_volume = volume is not None and volume < 0.8
        relative_ok = relative is None or relative >= -1.0
        if fresh and bullish_gap and (strong_volume or relative_ok):
            return "价量延续"
        if expired or (gap is not None and gap <= 0):
            return "动能衰减"
        if weak_volume:
            return "震荡"
        return "震荡"

    if snapshot.signal == "sell":
        bearish_gap = gap is not None and gap < 0
        if fresh and bearish_gap:
            return "价量延续"
        if expired or (gap is not None and gap >= 0):
            return "动能衰减"
        return "震荡"

    if gap is not None and abs(gap) < 0.5:
        return "震荡"
    if gap is not None and gap > 1.0:
        return "价量延续"
    if gap is not None and gap < -1.0:
        return "动能衰减"
    if age is not None and age <= SIGNAL_RECENT_DAYS:
        return "震荡"
    return "震荡"


def _classify_moneyflow_pattern(values: list[float]) -> str | None:
    if len(values) < 10:
        return None
    pattern = classify_flow_pattern_values(values)
    return None if pattern == "—" else pattern


def _price_pattern_to_flow_equiv(pattern: str, signal: SignalKind) -> str:
    if pattern == "价量延续":
        if signal == "buy":
            return "持续流入"
        if signal == "sell":
            return "持续流出"
        return "震荡"
    if pattern == "动能衰减":
        if signal == "buy":
            return "先入后出"
        if signal == "sell":
            return "先出后入"
        return "震荡"
    return "震荡"


def _price_momentum_delta(snapshot: SignalSnapshot) -> float:
    gap = snapshot.ma_gap_pct or 0.0
    relative = snapshot.relative_index_pct or 0.0
    volume = snapshot.volume_ratio_5d or 1.0
    return gap / 5.0 + relative / 20.0 + (volume - 1.0) * 2.0


def _moneyflow_momentum_delta(values: list[float]) -> float:
    if not values:
        return 0.0
    last_5 = sum(values[-5:])
    first_10 = sum(values[:10]) if len(values) >= 10 else sum(values[:-5]) if len(values) > 5 else 0.0
    return (last_5 - first_10) / 5000.0


def _flow_patterns_conflict(price_flow: str, moneyflow: str) -> bool:
    if price_flow == moneyflow:
        return False
    if price_flow == "震荡" or moneyflow == "震荡":
        return price_flow != moneyflow
    if price_flow in _BULLISH_FLOW and moneyflow in _BEARISH_FLOW:
        return True
    if price_flow in _BEARISH_FLOW and moneyflow in _BULLISH_FLOW:
        return True
    return True


def _build_outlook_days(
    flow_pattern: str,
    *,
    momentum_delta: float,
    forward_dates: tuple[str, ...],
) -> tuple[SectorFlowOutlookDay, ...]:
    base_seq = _PATTERN_BIAS_SEQUENCE.get(flow_pattern, ("震荡", "震荡", "震荡"))
    base_strength = _PATTERN_BASE_STRENGTH.get(flow_pattern, 0.42)
    momentum_boost = _clamp(momentum_delta / 10.0, -0.15, 0.15)
    core = base_strength + momentum_boost

    days: list[SectorFlowOutlookDay] = []
    for index, trade_date in enumerate(forward_dates):
        decay = _HORIZON_DECAY[index] if index < len(_HORIZON_DECAY) else _HORIZON_DECAY[-1]
        strength = _clamp(core * decay, 0.0, 1.0)
        bias = base_seq[index] if index < len(base_seq) else "震荡"
        if strength < _STRENGTH_NEUTRAL_THRESHOLD:
            bias = "震荡"
        days.append(
            SectorFlowOutlookDay(
                trade_date=trade_date,
                bias=bias,
                strength=round(strength, 2),
            )
        )
    return tuple(days)


def _build_rationale(
    *,
    price_pattern: str,
    moneyflow_pattern: str | None,
    signal_streak: int,
    snapshot: SignalSnapshot,
    conflict: bool,
) -> str:
    parts: list[str] = []
    if moneyflow_pattern:
        parts.append(f"资金{moneyflow_pattern}")
    parts.append(f"价量{price_pattern}")
    if conflict:
        parts.append("价量/资金分歧")
    if signal_streak > 0:
        parts.append(f"同向{signal_streak}日")
    if snapshot.ma_gap_pct is not None:
        parts.append(f"快慢距{snapshot.ma_gap_pct:+.2f}%")
    if snapshot.volume_ratio_5d is not None:
        parts.append(f"量比{snapshot.volume_ratio_5d:.2f}")
    if snapshot.relative_index_pct is not None:
        parts.append(f"相对300 {snapshot.relative_index_pct:+.2f}%")
    return "，".join(parts)


def _resolve_industry(vt_symbol: str, industry_map: Mapping[str, str]) -> str:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return ""
    return str(industry_map.get(item.ts_code) or "").strip()


def _load_sector_outlook_by_name(main_engine: MainEngine | None) -> dict[str, SectorFlowOutlookRow]:
    service = get_sector_flow_service(main_engine)
    if service is None:
        return {}
    try:
        outlook = service.load_continuation_outlook(sector_kind="industry")
    except Exception:
        return {}
    return {row.sector.name: row for row in outlook.rows if row.sector.name}


def build_stock_continuation(
    snapshot: SignalSnapshot | None,
    *,
    moneyflow_values: list[float] | None = None,
    industry: str = "",
    sector_outlook: SectorFlowOutlookRow | None = None,
) -> StockContinuationSnapshot | None:
    """由策略快照构建个股延续。"""
    if snapshot is None or snapshot.signal == "na" or signal_missing_kline(snapshot):
        return None

    price_pattern = _classify_price_pattern(snapshot)
    if price_pattern == "—":
        return None

    moneyflow_values = list(moneyflow_values or [])
    moneyflow_pattern = _classify_moneyflow_pattern(moneyflow_values)
    price_flow = _price_pattern_to_flow_equiv(price_pattern, snapshot.signal)
    forward_dates = iter_forward_trade_date_strs(count=STOCK_OUTLOOK_HORIZON_DAYS)

    conflict = False
    if moneyflow_pattern:
        conflict = _flow_patterns_conflict(price_flow, moneyflow_pattern)
        if conflict:
            flow_pattern = "震荡"
            headline = "震荡"
            momentum_delta = 0.0
        else:
            flow_pattern = moneyflow_pattern
            headline = moneyflow_pattern
            momentum_delta = _moneyflow_momentum_delta(moneyflow_values)
    else:
        flow_pattern = price_flow
        headline = price_pattern
        momentum_delta = _price_momentum_delta(snapshot)

    outlook_days = _build_outlook_days(flow_pattern, momentum_delta=momentum_delta, forward_dates=forward_dates)
    signal_streak = _signal_streak_days(snapshot)
    composite_strength = outlook_days[0].strength if outlook_days else 0.0

    sector_pattern = ""
    sector_outlook_compact = ""
    sector_id = ""
    if sector_outlook is not None:
        sector_pattern = sector_outlook.headline_pattern
        sector_outlook_compact = format_bias_compact(sector_outlook.days)
        sector_id = sector_outlook.sector.sector_id

    return StockContinuationSnapshot(
        vt_symbol=snapshot.vt_symbol,
        as_of=snapshot.as_of,
        headline_pattern=headline,
        outlook_days=outlook_days,
        composite_strength=composite_strength,
        price_pattern=price_pattern,
        moneyflow_pattern=moneyflow_pattern,
        signal_streak=signal_streak,
        rationale=_build_rationale(
            price_pattern=price_pattern,
            moneyflow_pattern=moneyflow_pattern,
            signal_streak=signal_streak,
            snapshot=snapshot,
            conflict=conflict,
        ),
        sector_name=industry,
        sector_id=sector_id,
        sector_pattern=sector_pattern,
        sector_outlook_compact=sector_outlook_compact,
        disclaimer=STOCK_CONTINUATION_DISCLAIMER,
    )


def build_continuation_batch(
    vt_symbols: list[str],
    signal_cache: Mapping[str, SignalSnapshot],
    *,
    main_engine: MainEngine | None = None,
    include_moneyflow: bool = True,
    include_sector_context: bool = True,
) -> dict[str, StockContinuationSnapshot]:
    industry_map = get_stock_industry_map() if include_sector_context else {}
    sector_outlook_by_name = _load_sector_outlook_by_name(main_engine) if include_sector_context else {}

    def _build_one(vt_symbol: str) -> tuple[str, StockContinuationSnapshot | None]:
        snapshot = lookup_by_vt_symbol(signal_cache, vt_symbol)
        moneyflow_values: list[float] | None = None
        if include_moneyflow:
            moneyflow_values = load_stock_moneyflow_values(vt_symbol)
        industry = _resolve_industry(vt_symbol, industry_map) if include_sector_context else ""
        sector_outlook = sector_outlook_by_name.get(industry) if industry else None
        continuation = build_stock_continuation(
            snapshot,
            moneyflow_values=moneyflow_values,
            industry=industry,
            sector_outlook=sector_outlook,
        )
        return vt_symbol, continuation

    if not vt_symbols:
        return {}

    workers = continuation_batch_max_workers(item_count=len(vt_symbols))
    pairs = run_parallel_map(vt_symbols, _build_one, max_workers=workers)
    return {vt_symbol: continuation for vt_symbol, continuation in pairs if continuation is not None}


def format_continuation_context_extra(continuation: StockContinuationSnapshot | None) -> str:
    """格式化个股延续摘要，供 AI 上下文或预填问句附加。"""
    if continuation is None or continuation.headline_pattern in {"", "—"}:
        return ""
    lines = [f"延续模式：{continuation.headline_pattern}"]
    if continuation.price_pattern not in {"", "—"}:
        lines.append(f"价量：{continuation.price_pattern}")
    if continuation.moneyflow_pattern:
        lines.append(f"资金：{continuation.moneyflow_pattern}")
    if continuation.outlook_days:
        tags = " / ".join(f"T+{index + 1}{day.bias}" for index, day in enumerate(continuation.outlook_days))
        compact = format_outlook_compact(continuation)
        lines.append(f"未来3日：{tags}（{compact}）")
    if continuation.rationale:
        lines.append(continuation.rationale)
    if continuation.sector_name:
        sector = continuation.sector_name
        if continuation.sector_pattern:
            sector += f" {continuation.sector_pattern}"
        if continuation.sector_outlook_compact and continuation.sector_outlook_compact != "—":
            sector += f" {continuation.sector_outlook_compact}"
        lines.append(f"板块环境：{sector}（与个股独立）")
    lines.append(continuation.disclaimer)
    return "\n".join(lines)


def format_signal_panel_context_extra(
    snapshot: SignalSnapshot | None,
    continuation: StockContinuationSnapshot | None = None,
    *,
    quote=None,
    slow_window: int = 20,
    fast_window: int = 10,
) -> str:
    """合并策略信号与个股延续，供信号区 AI 解读。"""
    from vnpy_ashare.services.signals.runtime import format_signal_context_extra

    parts: list[str] = []
    if snapshot is not None:
        signal_text = format_signal_context_extra(
            snapshot,
            quote=quote,
            slow_window=slow_window,
            fast_window=fast_window,
        )
        if signal_text:
            parts.append(signal_text)
    continuation_text = format_continuation_context_extra(continuation)
    if continuation_text:
        parts.append(f"【个股延续】\n{continuation_text}")
    return "\n\n".join(parts)


def continuation_snapshot_to_dict(continuation: StockContinuationSnapshot | None) -> dict[str, Any]:
    if continuation is None:
        return {}
    return {
        "headline_pattern": continuation.headline_pattern,
        "price_pattern": continuation.price_pattern,
        "moneyflow_pattern": continuation.moneyflow_pattern,
        "outlook_compact": format_outlook_compact(continuation),
        "composite_strength": continuation.composite_strength,
        "signal_streak": continuation.signal_streak,
        "rationale": continuation.rationale,
        "sector_name": continuation.sector_name,
        "sector_pattern": continuation.sector_pattern,
        "sector_outlook_compact": continuation.sector_outlook_compact,
        "disclaimer": continuation.disclaimer,
    }
