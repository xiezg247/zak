"""雷达页：未来·展望 loader（策略窗口 + 事件日历）。"""

from __future__ import annotations

from datetime import datetime

from vnpy_ashare.config.preferences.watchlist_signal import load_watchlist_signal_config
from vnpy_ashare.domain.signal_snapshot import (
    SIGNAL_RECENT_DAYS,
    SIGNAL_STRENGTH_STRONG,
    SignalSnapshot,
    dist_buy_pct,
    signal_age_days,
    signal_is_fresh,
    signal_missing_kline,
    signal_sort_key,
)
from vnpy_ashare.domain.symbols import parse_stock_symbol, vt_symbol_to_ts_code
from vnpy_ashare.quotes.radar_ai_cache import resolve_ai_hint, rows_fingerprint
from vnpy_ashare.quotes.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar_models import RadarCardData, RadarRow, merge_row_quotes
from vnpy_ashare.quotes.radar_pool import collect_horizon_candidates, name_map_for_symbols
from vnpy_ashare.quotes.radar_signals import build_signal_snapshot
from vnpy_ashare.services.stock.events import build_disclosure_upcoming_hints
from vnpy_ashare.storage.repositories.positions import load_position_rows


def _position_vt_set() -> set[str]:
    result: set[str] = set()
    for row in load_position_rows():
        result.add(f"{row['symbol']}.{row['exchange']}")
    return result


def _event_hint(vt_symbol: str) -> str:
    ts_code = vt_symbol_to_ts_code(vt_symbol)
    if not ts_code:
        return ""
    hints = build_disclosure_upcoming_hints(ts_code, limit=3)
    if not hints:
        return "—"
    return hints[0][:24]


def _has_near_unlock(vt_symbol: str, *, within_days: int = 3) -> bool:
    hint = _event_hint(vt_symbol)
    if "解禁" not in hint:
        return False
    prefix = hint.split(" ", 1)[0]
    try:
        days = int(prefix)
    except ValueError:
        return False
    return days <= within_days


def _last_price(vt_symbol: str, snapshot: SignalSnapshot) -> float | None:
    quote = merge_row_quotes({"vt_symbol": vt_symbol})
    raw = quote.get("last_price") or quote.get("close") or snapshot.last_close
    return float(raw) if isinstance(raw, (int, float)) else snapshot.last_close


def _matches_watch(snapshot: SignalSnapshot, *, last_price: float | None) -> bool:
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


def _matches_hold(snapshot: SignalSnapshot, *, last_price: float | None, in_position: bool) -> bool:
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
    if snapshot.fast_ma <= snapshot.slow_ma and not in_position:
        return False
    if last_price is not None and snapshot.ref_buy_price is not None and snapshot.signal == "buy":
        if last_price < snapshot.ref_buy_price:
            return False
    return True


def _watch_sort_key(snapshot: SignalSnapshot) -> tuple[int, float, float, str]:
    dist = dist_buy_pct(snapshot.ref_buy_price, snapshot.last_close)
    dist_abs = abs(dist) if dist is not None else 999.0
    strength = snapshot.strength if snapshot.strength is not None else float("-inf")
    return (signal_sort_key(snapshot.signal), strength, -dist_abs, snapshot.vt_symbol)


def _hold_sort_key(snapshot: SignalSnapshot, *, in_position: bool) -> tuple[int, float, int, str]:
    strength = snapshot.strength if snapshot.strength is not None else float("-inf")
    age = signal_age_days(snapshot)
    age_key = age if age is not None else 999
    return (0 if in_position else 1, -strength, age_key, snapshot.vt_symbol)


def _snapshot_row(snapshot: SignalSnapshot, *, name_map: dict[str, str], in_position: bool) -> RadarRow:
    item = parse_stock_symbol(snapshot.vt_symbol)
    name = name_map.get(snapshot.vt_symbol) or (item.name if item else "") or snapshot.vt_symbol
    symbol = item.symbol if item else snapshot.vt_symbol.split(".")[0]
    last_price = _last_price(snapshot.vt_symbol, snapshot)
    quote = merge_row_quotes({"vt_symbol": snapshot.vt_symbol})
    change_raw = quote.get("change_pct")
    change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
    strength_text = f"{snapshot.strength:.0f}" if snapshot.strength is not None else "—"
    event = _event_hint(snapshot.vt_symbol)
    pos_tag = "持仓" if in_position else snapshot.signal_label
    return RadarRow(
        vt_symbol=snapshot.vt_symbol,
        name=name,
        symbol=symbol,
        price=last_price,
        change_pct=change_pct,
        metric_label=pos_tag,
        metric_value=strength_text,
        sub_label="事件",
        sub_value=event,
    )


def build_outlook_digest(rows: tuple[RadarRow, ...], *, variant: str) -> str:
    """结构化摘要（供副标题与本地缓存）。"""
    if not rows:
        return ""
    buy = sum(1 for row in rows if row.metric_label in ("买入", "持仓"))
    hold = sum(1 for row in rows if row.metric_label == "观望")
    events = sum(1 for row in rows if row.sub_value not in ("—", ""))
    mode = "关注" if variant == "watch_next" else "可持"
    parts = [f"{mode} {len(rows)} 只"]
    if buy:
        parts.append(f"买入/持仓 {buy}")
    if hold:
        parts.append(f"观望 {hold}")
    if events:
        parts.append(f"有事件 {events}")
    return "摘要：" + " · ".join(parts)


def load_outlook_horizon(spec: RadarCardSpec, *, variant: str = "watch_next") -> RadarCardData:
    candidates = collect_horizon_candidates()
    if not candidates:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=f"策略窗口约 {SIGNAL_RECENT_DAYS} 日 · 非价格预测",
            rows=(),
            empty_message="暂无候选标的，请先添加自选或运行选股。",
            updated_at="",
        )

    config = load_watchlist_signal_config()
    name_map = name_map_for_symbols(candidates)
    positions = _position_vt_set()
    snapshots: list[tuple[SignalSnapshot, bool]] = []
    kline_missing = 0

    for vt_symbol in candidates:
        snapshot = build_signal_snapshot(vt_symbol, config=config)
        if snapshot is None:
            continue
        if signal_missing_kline(snapshot):
            kline_missing += 1
            continue
        in_position = vt_symbol in positions
        last_price = _last_price(vt_symbol, snapshot)
        if variant == "hold_next":
            if _matches_hold(snapshot, last_price=last_price, in_position=in_position):
                snapshots.append((snapshot, in_position))
        elif _matches_watch(snapshot, last_price=last_price):
            snapshots.append((snapshot, in_position))

    if variant == "hold_next":
        snapshots.sort(key=lambda item: _hold_sort_key(item[0], in_position=item[1]))
        label = "可持仓"
    else:
        snapshots.sort(key=lambda item: _watch_sort_key(item[0]), reverse=True)
        label = "未来关注"

    rows = tuple(_snapshot_row(item[0], name_map=name_map, in_position=item[1]) for item in snapshots[: spec.top_n])
    subtitle = f"{label} · 约 {SIGNAL_RECENT_DAYS} 日窗口 · 策略 {config.class_name} · 非价格预测"

    if not rows and kline_missing >= len(candidates) // 2:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=subtitle,
            rows=(),
            empty_message="本地日 K 不足，请先运行「全市场日 K」或「补全本地日 K」。",
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            total_count=len(candidates),
        )

    if not rows:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=subtitle,
            rows=(),
            empty_message=f"当前无符合「{label}」条件的标的（已扫描 {len(candidates)} 只）。",
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            total_count=len(candidates),
        )

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=rows,
        empty_message="",
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        total_count=len(rows),
        ai_hint=resolve_ai_hint(
            spec.id,
            variant=variant,
            fingerprint=rows_fingerprint(rows),
            digest=build_outlook_digest(rows, variant=variant),
        ),
    )


def build_outlook_ai_prompt(payload: dict[str, RadarCardData], *, variant: str) -> str:
    """生成未来展望卡 AI 解读预填文案。"""
    data = payload.get("outlook_horizon")
    if data is None or not data.rows:
        return ""
    mode = "未来几日关注" if variant == "watch_next" else "未来几日可持仓"
    lines = [
        f"请基于以下雷达「{mode}」快照，给出关注理由与风险提示：",
        "1. 说明策略信号窗口含义（约 5 个交易日，非涨跌预测）",
        "2. 逐只解读信号、强度与事件日历",
        "3. 给出不宜关注/不宜持有的情形",
        "4. 不得给出目标价或未在数据中的预测",
        "",
        data.subtitle,
        "",
    ]
    for row in data.rows:
        lines.append(f"- {row.name}({row.symbol}) {row.metric_label} 强度{row.metric_value} · {row.sub_label} {row.sub_value}")
    return "\n".join(lines)
