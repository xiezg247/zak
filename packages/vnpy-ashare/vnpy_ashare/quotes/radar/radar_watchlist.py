"""雷达页：自选·异动 loader。"""

from __future__ import annotations

from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig, load_watchlist_signal_config
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_horizon_scenario import batch_build_scenario_metrics, classify_scenario_hint
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow
from vnpy_ashare.quotes.radar.radar_moneyflow import enrich_quotes_with_moneyflow
from vnpy_ashare.quotes.radar.radar_pool import collect_personal_vt_symbols, name_map_for_symbols
from vnpy_ashare.quotes.radar.radar_signals import build_signal_snapshot, compute_signal_transitions
from vnpy_ashare.quotes.radar.radar_watchlist_quotes import has_quote_data, quotes_for_candidates
from vnpy_ashare.quotes.radar.radar_watchlist_score import row_from_quote, score_candidates

__all__ = [
    "load_watchlist_intraday",
]


def _scenario_hints_from_snapshots(
    vt_symbols: list[str],
    snapshots: dict[str, SignalSnapshot],
) -> dict[str, str]:
    """从已有 SignalSnapshot 计算情景标签（不重新加载日K）。"""
    metrics_list = batch_build_scenario_metrics(vt_symbols, snapshots)
    hints: dict[str, str] = {}
    for metrics in metrics_list:
        hint = classify_scenario_hint(metrics)
        if hint:
            hints[metrics.snapshot.vt_symbol] = hint
    return hints


def _compute_scenario_hints(
    vt_symbols: list[str],
    *,
    config: WatchlistSignalConfig | None = None,
    snapshots: dict[str, SignalSnapshot] | None = None,
) -> dict[str, str]:
    """为 Top N 异动标的计算轻量 5 日统计情景（非价格预测）。

    snapshots 可从 compute_signal_transitions(return_snapshots=True) 传入，避免重复 load_scope_bars。
    """
    if not vt_symbols:
        return {}
    if snapshots is not None and all(vt in snapshots for vt in vt_symbols):
        return _scenario_hints_from_snapshots(vt_symbols, snapshots)
    cfg = (config or load_watchlist_signal_config()).normalized()
    built: dict[str, SignalSnapshot] = {}
    for vt_symbol in vt_symbols:
        if snapshots is not None and vt_symbol in snapshots:
            built[vt_symbol] = snapshots[vt_symbol]
        else:
            snapshot = build_signal_snapshot(vt_symbol, config=cfg)
            if snapshot is not None:
                built[vt_symbol] = snapshot
    if not built:
        return {}
    return _scenario_hints_from_snapshots(list(built.keys()), built)


def load_watchlist_intraday(spec: RadarCardSpec) -> RadarCardData:
    from vnpy_ashare.screener.hard_filters import filter_vt_symbols_by_recipe_market_board

    candidates = filter_vt_symbols_by_recipe_market_board(collect_personal_vt_symbols())
    if not candidates:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="",
            rows=(),
            empty_message="自选池为空，请先添加自选或持仓。",
            updated_at="",
        )

    config = load_watchlist_signal_config()
    transitions: dict[str, str] = {}
    signal_snapshots: dict[str, SignalSnapshot] = {}
    try:
        transitions, signal_snapshots = compute_signal_transitions(
            candidates, config=config, max_compute=12, return_snapshots=True
        )  # type: ignore[assignment]
    except Exception:
        transitions = {}

    quotes_by_vt = quotes_for_candidates(candidates)
    quotes_by_vt = enrich_quotes_with_moneyflow(quotes_by_vt)
    name_map = name_map_for_symbols(candidates)
    has_any_quote = any(has_quote_data(row) for row in quotes_by_vt.values())

    scored = score_candidates(candidates, quotes_by_vt, transitions, anomaly_only=True)
    fallback = False
    if not scored:
        scored = score_candidates(candidates, quotes_by_vt, transitions, anomaly_only=False)
        fallback = bool(scored)

    top_scored = scored[: spec.top_n]
    scenario_hints: dict[str, str] = {}
    try:
        scenario_hints = _compute_scenario_hints(
            [vt_symbol for vt_symbol, _row, _score, _transition in top_scored],
            config=config,
            snapshots=signal_snapshots,
        )
    except Exception:
        scenario_hints = {}

    rows: list[RadarRow] = []
    transition_count = 0
    scenario_count = 0
    for vt_symbol, row, _score, transition in top_scored:
        parsed = row_from_quote(
            vt_symbol,
            row,
            name_map=name_map,
            transition=transition,
            scenario_hint=scenario_hints.get(vt_symbol),
        )
        if parsed is not None:
            rows.append(parsed)
            if transition:
                transition_count += 1
            if scenario_hints.get(vt_symbol):
                scenario_count += 1

    if fallback:
        subtitle_parts = [f"涨跌幅前列 · {len(rows)} / {len(candidates)} 只（今日整体波动较小）"]
    else:
        subtitle_parts = [f"自选异动 Top {len(rows)} / {len(candidates)} 只"]
    if transition_count:
        subtitle_parts.append(f"信号跃迁 {transition_count}")
    if scenario_count:
        subtitle_parts.append(f"5日情景 {scenario_count}")
    subtitle = " · ".join(subtitle_parts)

    if not rows and not has_any_quote:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=f"扫描 {len(candidates)} 只自选",
            rows=(),
            empty_message="暂无行情数据，请先采集行情或打开「市场」页。",
            updated_at="",
        )

    if not rows:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=f"扫描 {len(candidates)} 只自选",
            rows=(),
            empty_message="自选池今日波动平缓，暂无显著异动。",
            updated_at="",
            total_count=len(candidates),
        )

    ai_hint_parts: list[str] = []
    if transitions:
        sample = "、".join(list(transitions.values())[:3])
        ai_hint_parts.append(f"信号跃迁 {len(transitions)} 只：{sample}")
    if scenario_count:
        scenario_sample = "、".join(
            f"{name_map.get(vt, vt)} {hint}" for vt, hint in list(scenario_hints.items())[:3]
        )
        ai_hint_parts.append(f"5日统计情景 {scenario_count} 只（非价格预测）：{scenario_sample}")
    ai_hint = " · ".join(ai_hint_parts)

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=tuple(rows),
        empty_message="",
        updated_at="",
        total_count=len(rows),
        ai_hint=ai_hint,
    )
