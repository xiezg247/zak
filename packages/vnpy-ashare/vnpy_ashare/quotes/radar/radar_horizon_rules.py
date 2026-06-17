"""雷达未来展望：策略匹配、排序与行构建（无 IO 循环依赖）。"""

from __future__ import annotations

from vnpy_ashare.domain.symbols import parse_stock_symbol, vt_symbol_to_ts_code
from vnpy_ashare.domain.trading.signal_snapshot import (
    SIGNAL_STRENGTH_STRONG,
    SignalSnapshot,
    dist_buy_pct,
    signal_age_days,
    signal_is_fresh,
    signal_missing_kline,
    signal_sort_key,
)
from vnpy_ashare.quotes.radar.radar_models import RadarRow, merge_row_quotes
from vnpy_ashare.services.stock.events import build_disclosure_upcoming_hints


def event_hint(vt_symbol: str) -> str:
    ts_code = vt_symbol_to_ts_code(vt_symbol)
    if not ts_code:
        return ""
    hints = build_disclosure_upcoming_hints(ts_code, limit=3)
    if not hints:
        return "—"
    return hints[0][:24]


def _has_near_unlock(vt_symbol: str, *, within_days: int = 3) -> bool:
    hint = event_hint(vt_symbol)
    if "解禁" not in hint:
        return False
    prefix = hint.split(" ", 1)[0]
    try:
        days = int(prefix)
    except ValueError:
        return False
    return days <= within_days


def last_price_for_snapshot(vt_symbol: str, snapshot: SignalSnapshot) -> float | None:
    quote = merge_row_quotes({"vt_symbol": vt_symbol})
    raw = quote.get("last_price") or quote.get("close") or snapshot.last_close
    return float(raw) if isinstance(raw, (int, float)) else snapshot.last_close


def matches_watch(snapshot: SignalSnapshot, *, last_price: float | None) -> bool:
    if signal_missing_kline(snapshot):
        return False
    if snapshot.signal == "sell" and signal_is_fresh(snapshot):
        return False
    if _has_near_unlock(snapshot.vt_symbol):
        return False
    if snapshot.signal == "buy" and signal_is_fresh(snapshot):
        return True
    dist = dist_buy_pct(snapshot.ref_buy_price, last_price)
    if snapshot.signal == "hold" and snapshot.fast_ma and snapshot.slow_ma:
        if snapshot.fast_ma > snapshot.slow_ma and dist is not None and abs(dist) <= 8.0:
            return True
    last_cross = None
    for reason in snapshot.reasons:
        if "金叉" in reason:
            last_cross = "golden"
            break
    if last_cross == "golden" and signal_is_fresh(snapshot):
        return True
    if snapshot.strength is not None and snapshot.strength >= SIGNAL_STRENGTH_STRONG and snapshot.signal in ("buy", "hold"):
        if snapshot.fast_ma and snapshot.slow_ma and snapshot.fast_ma >= snapshot.slow_ma:
            return True
    return False


def matches_hold(snapshot: SignalSnapshot, *, last_price: float | None) -> bool:
    if signal_missing_kline(snapshot):
        return False
    if snapshot.signal == "sell" and signal_is_fresh(snapshot):
        return False
    if _has_near_unlock(snapshot.vt_symbol):
        return False
    if snapshot.signal not in ("buy", "hold"):
        return False
    if snapshot.fast_ma is None or snapshot.slow_ma is None:
        return False
    if snapshot.fast_ma <= snapshot.slow_ma:
        return False
    if last_price is not None and snapshot.ref_buy_price is not None and snapshot.signal == "buy":
        if last_price < snapshot.ref_buy_price:
            return False
    return True


def watch_sort_key(snapshot: SignalSnapshot) -> tuple[int, float, float, str]:
    dist = dist_buy_pct(snapshot.ref_buy_price, snapshot.last_close)
    dist_abs = abs(dist) if dist is not None else 999.0
    strength = snapshot.strength if snapshot.strength is not None else float("-inf")
    return (signal_sort_key(snapshot.signal), strength, -dist_abs, snapshot.vt_symbol)


def hold_sort_key(snapshot: SignalSnapshot) -> tuple[float, int, str]:
    strength = snapshot.strength if snapshot.strength is not None else float("-inf")
    age = signal_age_days(snapshot)
    age_key = age if age is not None else 999
    return (-strength, age_key, snapshot.vt_symbol)


def outlook_sort_key(snapshot: SignalSnapshot, *, variant: str) -> tuple:
    if variant == "hold_next":
        return hold_sort_key(snapshot)
    return watch_sort_key(snapshot)


def outlook_judgment_subline(
    snapshot: SignalSnapshot,
    *,
    scenario_hint: str | None = None,
    last_price: float | None = None,
) -> tuple[str, str]:
    """未来卡副指标：优先 5 日统计情景，否则给出策略判断（非事件日历）。"""
    if scenario_hint:
        return "5日情景", scenario_hint
    dist = dist_buy_pct(snapshot.ref_buy_price, last_price or snapshot.last_close)
    if dist is not None and snapshot.signal in ("buy", "hold"):
        return "距买点", f"{dist:+.1f}%"
    summary = str(snapshot.reason_summary or "").strip()
    if summary:
        return "判断", summary[:24]
    for reason in snapshot.reasons:
        text = str(reason).strip()
        if text:
            return "判断", text[:24]
    return "判断", "—"


def filter_outlook_snapshots(
    snapshots: list[SignalSnapshot],
    *,
    variant: str,
) -> list[SignalSnapshot]:
    matched: list[SignalSnapshot] = []
    for snapshot in snapshots:
        last_price = last_price_for_snapshot(snapshot.vt_symbol, snapshot)
        if variant == "hold_next":
            if matches_hold(snapshot, last_price=last_price):
                matched.append(snapshot)
        elif matches_watch(snapshot, last_price=last_price):
            matched.append(snapshot)
    return matched


def snapshot_to_row(
    snapshot: SignalSnapshot,
    *,
    name_map: dict[str, str],
    scenario_hint: str | None = None,
) -> RadarRow:
    item = parse_stock_symbol(snapshot.vt_symbol)
    name = name_map.get(snapshot.vt_symbol) or (item.name if item else "") or snapshot.vt_symbol
    symbol = item.symbol if item else snapshot.vt_symbol.split(".")[0]
    last_price = last_price_for_snapshot(snapshot.vt_symbol, snapshot)
    quote = merge_row_quotes({"vt_symbol": snapshot.vt_symbol})
    change_raw = quote.get("change_pct")
    change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
    strength_text = f"{snapshot.strength:.0f}" if snapshot.strength is not None else "—"
    sub_label, sub_value = outlook_judgment_subline(
        snapshot,
        scenario_hint=scenario_hint,
        last_price=last_price,
    )
    return RadarRow(
        vt_symbol=snapshot.vt_symbol,
        name=name,
        symbol=symbol,
        price=last_price,
        change_pct=change_pct,
        metric_label=snapshot.signal_label,
        metric_value=strength_text,
        sub_label=sub_label,
        sub_value=sub_value,
    )


def build_outlook_rows(
    snapshots: tuple[SignalSnapshot, ...],
    *,
    name_map: dict[str, str],
    scenario_hints: dict[str, str] | None = None,
) -> tuple[RadarRow, ...]:
    hints = scenario_hints or {}
    return tuple(snapshot_to_row(snapshot, name_map=name_map, scenario_hint=hints.get(snapshot.vt_symbol)) for snapshot in snapshots)
