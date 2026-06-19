"""板块未来 N 日资金展望：策略聚合口径（B）。"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timedelta

from vnpy_ashare.domain.market.sector_flow import (
    OUTLOOK_DISCLAIMER,
    OUTLOOK_HORIZON_DAYS,
    SectorFlowOutlookDay,
    SectorFlowOutlookRow,
    SectorFlowOutlookSnapshot,
    SectorFlowRow,
    SectorFlowSnapshot,
)
from vnpy_ashare.domain.radar.horizon_cache import HorizonCacheEntry
from vnpy_ashare.domain.time.trade_dates import iter_forward_trade_date_strs
from vnpy_ashare.domain.trading.signal_snapshot import signal_missing_kline
from vnpy_ashare.integrations.tushare.sw_industry import member_rows_vt_symbols_for_l2
from vnpy_ashare.services.sector_constituents import resolve_concept_vt_symbols

_HORIZON_DECAY = (1.0, 0.72, 0.50)
_SCORE_BULLISH = 0.55
_SCORE_BEARISH = 0.20
_MIN_MEMBERS_FOR_CONFIDENCE = 3
_SECTOR_STRATEGY_SCAN_TOP_N = 48
_SECTOR_STRATEGY_PREFILTER_TOP = 300
_SECTOR_STRATEGY_CACHE_TTL_HOURS = 24


def _sector_member_symbols(sector: SectorFlowRow) -> set[str]:
    if sector.sector_kind == "concept":
        return set(resolve_concept_vt_symbols(sector))
    symbols = member_rows_vt_symbols_for_l2(sector.name)
    if symbols:
        return set(symbols)
    return set()


def _stock_hit_score(metric_label: str, *, pool: str) -> float:
    label = str(metric_label or "").strip()
    if label == "买入":
        score = 2.0
    elif label == "观望":
        score = 1.0
    else:
        score = 0.0
    if pool == "watch_next" and label == "买入":
        score += 0.5
    if pool == "hold_next" and label in {"买入", "观望"}:
        score += 0.25
    return score


def _index_horizon_hits(
    watch_entry: HorizonCacheEntry | None,
    hold_entry: HorizonCacheEntry | None,
) -> dict[str, float]:
    scores: dict[str, float] = {}
    if watch_entry is not None:
        for row in watch_entry.rows:
            scores[row.vt_symbol] = scores.get(row.vt_symbol, 0.0) + _stock_hit_score(row.metric_label, pool="watch_next")
    if hold_entry is not None:
        for row in hold_entry.rows:
            scores[row.vt_symbol] = scores.get(row.vt_symbol, 0.0) + _stock_hit_score(row.metric_label, pool="hold_next")
    return scores


def _score_to_bias(score: float) -> str:
    if score >= _SCORE_BULLISH:
        return "偏多"
    if score <= _SCORE_BEARISH:
        return "偏空"
    return "震荡"


def _strategy_rationale(
    *,
    buy_count: int,
    hold_count: int,
    watch_count: int,
    member_count: int,
    sample_limited: bool,
) -> str:
    parts = [f"成分{member_count}只，策略命中买入{buy_count}/观望{hold_count}/关注{watch_count}"]
    if sample_limited:
        parts.append("样本偏少，展望仅供参考")
    return "，".join(parts)


def _strategy_day_rows(
    raw_score: float,
    forward_dates: tuple[str, ...],
    *,
    sample_limited: bool,
) -> tuple[SectorFlowOutlookDay, ...]:
    days: list[SectorFlowOutlookDay] = []
    for index, trade_date in enumerate(forward_dates):
        decay = _HORIZON_DECAY[index] if index < len(_HORIZON_DECAY) else _HORIZON_DECAY[-1]
        strength = max(0.0, min(1.0, raw_score * decay))
        if sample_limited:
            strength = min(strength, 0.65)
        bias = _score_to_bias(strength)
        days.append(
            SectorFlowOutlookDay(
                trade_date=trade_date,
                bias=bias,
                strength=round(strength, 2),
            )
        )
    return tuple(days)


def resolve_strategy_signal_config(strategy_class: str | None = None):
    from strategies.signals import STRATEGY_SIGNAL_DEFAULTS
    from vnpy_ashare.config.preferences.watchlist_signal import DEFAULT_CLASS, WatchlistSignalConfig
    from vnpy_ashare.quotes.radar.outlook_strategy_prefs import (
        _normalize_class_name,
        load_sector_flow_outlook_signal_config,
    )

    cleaned = str(strategy_class or "").strip()
    if cleaned:
        class_name = _normalize_class_name(cleaned)
    else:
        class_name = load_sector_flow_outlook_signal_config().class_name
    fast, slow = STRATEGY_SIGNAL_DEFAULTS.get(class_name, STRATEGY_SIGNAL_DEFAULTS[DEFAULT_CLASS])
    return WatchlistSignalConfig(class_name=class_name, fast_window=fast, slow_window=slow).normalized()


def _strategy_horizon_cache_entries(strategy_class: str | None = None) -> tuple[HorizonCacheEntry | None, HorizonCacheEntry | None]:
    from vnpy_ashare.quotes.radar.radar_horizon_cache import get_horizon_cache

    config = resolve_strategy_signal_config(strategy_class)
    key = config.cache_key()
    return (
        get_horizon_cache("watch_next", strategy_key=key),
        get_horizon_cache("hold_next", strategy_key=key),
    )


def _parse_horizon_computed_at(value: str) -> datetime | None:
    from vnpy_ashare.domain.time.china import CHINA_TZ, DATETIME_MINUTE_FMT

    cleaned = str(value or "").strip()
    if not cleaned:
        return None
    for fmt in (DATETIME_MINUTE_FMT, "%Y-%m-%d %H:%M:%S"):
        try:
            parsed = datetime.strptime(cleaned, fmt)
            return parsed.replace(tzinfo=CHINA_TZ)
        except ValueError:
            continue
    return None


def strategy_outlook_cache_computed_at(strategy_class: str | None = None) -> datetime | None:
    """返回 watch/hold 缓存中较早的 computed_at（用于过期判断）。"""
    watch_entry, hold_entry = _strategy_horizon_cache_entries(strategy_class)
    stamps: list[datetime] = []
    for entry in (watch_entry, hold_entry):
        if entry is None:
            continue
        parsed = _parse_horizon_computed_at(entry.computed_at)
        if parsed is not None:
            stamps.append(parsed)
    if not stamps:
        return None
    return min(stamps)


def strategy_outlook_cache_ready(strategy_class: str | None = None) -> bool:
    watch_entry, hold_entry = _strategy_horizon_cache_entries(strategy_class)
    return watch_entry is not None or hold_entry is not None


def strategy_outlook_cache_expired(
    strategy_class: str | None = None,
    *,
    ttl_hours: int = _SECTOR_STRATEGY_CACHE_TTL_HOURS,
) -> bool:
    if not strategy_outlook_cache_ready(strategy_class):
        return True
    computed_at = strategy_outlook_cache_computed_at(strategy_class)
    if computed_at is None:
        return True
    from vnpy_ashare.domain.time.china import china_now

    return china_now() - computed_at >= timedelta(hours=max(1, int(ttl_hours)))


def strategy_outlook_cache_fresh(strategy_class: str | None = None) -> bool:
    return strategy_outlook_cache_ready(strategy_class) and not strategy_outlook_cache_expired(strategy_class)


def scan_strategy_outlook_cache(
    strategy_class: str,
    *,
    top_n: int = _SECTOR_STRATEGY_SCAN_TOP_N,
    max_prefilter: int = _SECTOR_STRATEGY_PREFILTER_TOP,
    on_progress: Callable[[str], None] | None = None,
) -> str:
    """为指定策略扫描关注/可持并写入本地缓存（供板块资金策略 B，轻量粗筛池）。"""
    from vnpy_ashare.quotes.radar.outlook_strategy_prefs import outlook_strategy_label
    from vnpy_ashare.quotes.radar.radar_horizon_scan import (
        batch_build_signal_snapshots,
        collect_outlook_exclusion_vt_symbols,
        prefilter_horizon_universe,
        scan_horizon_variant,
    )

    def report(message: str) -> None:
        if on_progress is not None:
            on_progress(message)

    config = resolve_strategy_signal_config(strategy_class)
    exclusion = collect_outlook_exclusion_vt_symbols()
    report("粗筛流动性池…")
    prefilter, base_stats = prefilter_horizon_universe(
        exclusion,
        config=config,
        max_items=max_prefilter,
    )
    total = len(prefilter)
    report(f"计算信号 0/{total}…")

    def _on_signal_complete(index: int, _item: str, _result: object) -> None:
        if total <= 0:
            return
        step = max(1, total // 10)
        if index == 0 or index + 1 == total or (index + 1) % step == 0:
            report(f"计算信号 {index + 1}/{total}…")

    snapshots = batch_build_signal_snapshots(
        prefilter,
        config=config,
        on_complete=_on_signal_complete,
    )
    report("筛选关注/可持…")
    watch = scan_horizon_variant(
        "watch_next",
        top_n=top_n,
        config=config,
        exclusion=exclusion,
        prefilter=prefilter,
        snapshots=snapshots,
        base_stats=base_stats,
    )
    hold = scan_horizon_variant(
        "hold_next",
        top_n=top_n,
        config=config,
        exclusion=exclusion,
        prefilter=prefilter,
        snapshots=snapshots,
        base_stats=base_stats,
    )
    label = outlook_strategy_label(config.class_name)
    return f"「{label}」策略扫描完成：关注 {len(watch.rows)} / 可持 {len(hold.rows)}（粗筛 {total} 只）"


def build_strategy_outlook(
    snapshot: SectorFlowSnapshot,
    *,
    horizon_days: int = OUTLOOK_HORIZON_DAYS,
    strategy_class: str | None = None,
    strategy_key: str | None = None,
    watch_entry: HorizonCacheEntry | None = None,
    hold_entry: HorizonCacheEntry | None = None,
) -> SectorFlowOutlookSnapshot:
    from vnpy_ashare.quotes.radar.outlook_strategy_prefs import (
        load_sector_flow_outlook_signal_config,
        outlook_strategy_label,
    )

    if str(strategy_key or "").strip():
        resolved_key = str(strategy_key).strip()
        resolved_class = str(strategy_class or "").strip() or None
    elif str(strategy_class or "").strip():
        config = resolve_strategy_signal_config(strategy_class)
        resolved_class = config.class_name
        resolved_key = config.cache_key()
    else:
        config = load_sector_flow_outlook_signal_config()
        resolved_key = config.cache_key()
        resolved_class = config.class_name

    strategy_label = outlook_strategy_label(resolved_class) if resolved_class else resolved_key

    forward_dates = iter_forward_trade_date_strs(count=horizon_days)

    if watch_entry is None or hold_entry is None:
        from vnpy_ashare.quotes.radar.radar_horizon_cache import get_horizon_cache

        if watch_entry is None:
            watch_entry = get_horizon_cache("watch_next", strategy_key=resolved_key)
        if hold_entry is None:
            hold_entry = get_horizon_cache("hold_next", strategy_key=resolved_key)

    cache_missing = watch_entry is None and hold_entry is None

    hit_scores = _index_horizon_hits(watch_entry, hold_entry)
    watch_symbols = {row.vt_symbol for row in watch_entry.rows} if watch_entry else set()
    hold_symbols = {row.vt_symbol for row in hold_entry.rows} if hold_entry else set()
    label_by_symbol: dict[str, str] = {}
    if watch_entry:
        for row in watch_entry.rows:
            label_by_symbol[row.vt_symbol] = row.metric_label
    if hold_entry:
        for row in hold_entry.rows:
            label_by_symbol.setdefault(row.vt_symbol, row.metric_label)

    sectors: dict[str, SectorFlowRow] = {}
    for row in (*snapshot.inflow_rows, *snapshot.outflow_rows):
        sectors[row.sector_id] = row

    outlook_rows: list[SectorFlowOutlookRow] = []
    if not cache_missing:
        for sector in sectors.values():
            members = _sector_member_symbols(sector)
            if not members:
                continue
            hits = members & set(hit_scores)
            buy_count = sum(1 for symbol in hits if label_by_symbol.get(symbol) == "买入")
            hold_count = sum(1 for symbol in hits if label_by_symbol.get(symbol) == "观望")
            watch_count = len((members & watch_symbols) - (members & hold_symbols))
            raw_score = sum(hit_scores.get(symbol, 0.0) for symbol in hits) / max(len(members), 1) / 2.5
            sample_limited = len(members) < _MIN_MEMBERS_FOR_CONFIDENCE
            days = _strategy_day_rows(raw_score, forward_dates, sample_limited=sample_limited)
            headline = f"买入{buy_count}/观望{hold_count}/关注{watch_count}"
            outlook_rows.append(
                SectorFlowOutlookRow(
                    sector=sector,
                    days=days,
                    headline_pattern=headline,
                    rationale=_strategy_rationale(
                        buy_count=buy_count,
                        hold_count=hold_count,
                        watch_count=watch_count,
                        member_count=len(members),
                        sample_limited=sample_limited,
                    ),
                    source="strategy",
                )
            )

        outlook_rows.sort(
            key=lambda item: (
                -(item.days[0].strength if item.days else 0.0),
                item.sector.name,
            )
        )

    empty_hint = ""
    if not snapshot.rows:
        empty_hint = snapshot.empty_hint or "暂无板块数据"
    elif watch_entry is None and hold_entry is None:
        empty_hint = f"策略B·{strategy_label} 暂无本地缓存，请点击「扫描策略B」"
    elif not outlook_rows:
        empty_hint = f"策略B·{strategy_label} 与当前行业成分无交集（展望池 {len(watch_symbols | hold_symbols)} 只）"

    updated_at = snapshot.updated_at or ""
    if updated_at and "策略展望" not in updated_at:
        updated_at = f"{updated_at} · 策略展望·{strategy_label}"

    return SectorFlowOutlookSnapshot(
        forward_dates=forward_dates,
        rows=tuple(outlook_rows),
        sector_kind=snapshot.sector_kind or "industry",
        source="strategy",
        updated_at=updated_at,
        empty_hint=empty_hint,
        disclaimer=OUTLOOK_DISCLAIMER,
        data_mode=snapshot.data_mode if snapshot.data_mode != "intraday" else "official_dc",
    )


def build_sector_strategy_outlook_row(
    sector: SectorFlowRow,
    *,
    strategy_class: str | None = None,
    forward_dates: tuple[str, ...] | None = None,
    horizon_days: int = OUTLOOK_HORIZON_DAYS,
) -> SectorFlowOutlookRow:
    """对单板块成分股跑策略信号并聚合为板块级展望（非全市场扫描）。"""
    from vnpy_ashare.quotes.radar.radar_horizon_rules import last_price_for_snapshot, matches_hold, matches_watch
    from vnpy_ashare.quotes.radar.radar_horizon_scan import batch_build_signal_snapshots

    config = resolve_strategy_signal_config(strategy_class)
    members = sorted(_sector_member_symbols(sector))
    if not members:
        raise ValueError(f"未找到板块「{sector.name}」成分股映射")

    dates = forward_dates or iter_forward_trade_date_strs(count=horizon_days)
    snapshots = batch_build_signal_snapshots(members, config=config)

    watch_symbols: set[str] = set()
    hold_symbols: set[str] = set()
    label_by_symbol: dict[str, str] = {}
    valid_symbols: list[str] = []

    for vt_symbol, snapshot in snapshots.items():
        if signal_missing_kline(snapshot):
            continue
        valid_symbols.append(vt_symbol)
        label_by_symbol[vt_symbol] = str(snapshot.signal_label or "").strip()
        last_price = last_price_for_snapshot(vt_symbol, snapshot)
        if matches_hold(snapshot, last_price=last_price):
            hold_symbols.add(vt_symbol)
        elif matches_watch(snapshot, last_price=last_price):
            watch_symbols.add(vt_symbol)

    member_set = set(members)
    hits = member_set & set(valid_symbols)
    buy_count = sum(1 for symbol in hits if label_by_symbol.get(symbol) == "买入")
    hold_count = sum(1 for symbol in hits if label_by_symbol.get(symbol) == "观望")
    watch_count = len((watch_symbols & hits) - hold_symbols)

    hit_scores: dict[str, float] = {}
    for symbol in hits:
        pool = "hold_next" if symbol in hold_symbols else "watch_next" if symbol in watch_symbols else ""
        hit_scores[symbol] = _stock_hit_score(label_by_symbol.get(symbol, ""), pool=pool)

    raw_score = sum(hit_scores.values()) / max(len(members), 1) / 2.5
    sample_limited = len(members) < _MIN_MEMBERS_FOR_CONFIDENCE
    days = _strategy_day_rows(raw_score, dates, sample_limited=sample_limited)
    headline = f"买入{buy_count}/观望{hold_count}/关注{watch_count}"
    rationale = _strategy_rationale(
        buy_count=buy_count,
        hold_count=hold_count,
        watch_count=watch_count,
        member_count=len(members),
        sample_limited=sample_limited,
    )
    if len(valid_symbols) < len(members):
        missing = len(members) - len(valid_symbols)
        rationale = f"{rationale}，{missing}只成分K线不足未计入"

    return SectorFlowOutlookRow(
        sector=sector,
        days=days,
        headline_pattern=headline,
        rationale=rationale,
        source="strategy",
    )


def classify_sector_resonance(
    continuation: SectorFlowOutlookRow | None,
    strategy: SectorFlowOutlookRow | None,
) -> str:
    if continuation is None or strategy is None or not continuation.days or not strategy.days:
        return "—"
    cont_bias = continuation.days[0].bias
    strat_bias = strategy.days[0].bias
    if cont_bias == strat_bias:
        return "同向"
    return "背离"


def format_strategy_ai_lines(
    outlook: SectorFlowOutlookSnapshot,
    *,
    limit: int = 8,
) -> list[str]:
    if not outlook.rows:
        return []
    kind_label = "概念" if outlook.sector_kind == "concept" else "行业"
    lines = [f"未来{len(outlook.forward_dates)}日{kind_label}策略聚合展望（{outlook.disclaimer}）："]
    for row in outlook.rows[: max(1, limit)]:
        day_tags = " / ".join(f"T+{index + 1}{day.bias}" for index, day in enumerate(row.days))
        lines.append(f"· {row.sector.name} {row.headline_pattern} {day_tags} — {row.rationale}")
    return lines


__all__ = [
    "build_sector_strategy_outlook_row",
    "build_strategy_outlook",
    "classify_sector_resonance",
    "format_strategy_ai_lines",
    "resolve_strategy_signal_config",
    "scan_strategy_outlook_cache",
    "strategy_outlook_cache_computed_at",
    "strategy_outlook_cache_expired",
    "strategy_outlook_cache_fresh",
    "strategy_outlook_cache_ready",
]
