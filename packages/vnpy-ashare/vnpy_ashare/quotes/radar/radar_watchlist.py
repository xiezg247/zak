"""雷达页：自选·异动 loader。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.config.preferences.watchlist_signal import WatchlistSignalConfig, load_watchlist_signal_config
from vnpy_ashare.domain.market.quote_row import QuoteRow, QuoteRowLike, QuoteRowsLike
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol, parse_tickflow_symbol
from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.quotes.format import format_amount, format_pct
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_horizon_scenario import batch_build_scenario_metrics, classify_scenario_hint
from vnpy_ashare.quotes.radar.radar_models import (
    RadarCardData,
    RadarRow,
    merge_row_quotes,
    quote_map,
)
from vnpy_ashare.quotes.radar.radar_moneyflow import (
    enrich_quotes_with_moneyflow,
    moneyflow_score_boost,
    watchlist_moneyflow_metric,
)
from vnpy_ashare.quotes.radar.radar_pool import collect_personal_vt_symbols, name_map_for_symbols
from vnpy_ashare.quotes.radar.radar_signals import build_signal_snapshot, compute_signal_transitions
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError

SIGNAL_TRANSITION_BOOST = 35.0


def _ingest_quote_row(
    row: QuoteRowLike,
    *,
    by_vt: dict[str, dict[str, Any]],
    by_symbol: dict[str, dict[str, Any]],
) -> None:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    symbol = str(row.get("symbol") or "").strip()
    if not vt_symbol and symbol:
        item = parse_stock_symbol(symbol)
        if item is not None:
            vt_symbol = item.vt_symbol
            row = dict(row)
            row["vt_symbol"] = vt_symbol
    if vt_symbol:
        by_vt[vt_symbol] = dict(row)
    if symbol:
        by_symbol[symbol] = dict(row)


def _quotes_for_candidates(candidates: list[str]) -> dict[str, dict[str, Any]]:
    """自选 vt_symbol → 行情行（缓存 / 全市场 / Redis 逐只补全）。"""
    by_vt: dict[str, dict[str, Any]] = {}
    by_symbol: dict[str, dict[str, Any]] = {}

    for row in quote_map().values():
        _ingest_quote_row(row, by_vt=by_vt, by_symbol=by_symbol)

    try:
        snapshot = load_screening_quote_snapshot()
        for row in snapshot.rows:
            _ingest_quote_row(dict(row), by_vt=by_vt, by_symbol=by_symbol)
    except MarketQuotesLoadError:
        pass

    missing_tf: list[str] = []
    for vt_symbol in candidates:
        if vt_symbol in by_vt:
            continue
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            continue
        if item.symbol in by_symbol:
            merged = dict(by_symbol[item.symbol])
            merged["vt_symbol"] = vt_symbol
            by_vt[vt_symbol] = merged
            continue
        missing_tf.append(item.tickflow_symbol)

    if missing_tf:
        try:
            quotes = RedisQuoteStore().get_quotes(missing_tf)
            for tf_symbol, quote in quotes.items():
                item = parse_tickflow_symbol(tf_symbol, quote.name)
                if item is None:
                    continue
                _ingest_quote_row(
                    {
                        "vt_symbol": item.vt_symbol,
                        "symbol": item.symbol,
                        "name": quote.name or item.name,
                        "last_price": quote.last_price,
                        "close": quote.last_price,
                        "change_pct": quote.change_pct,
                        "turnover_rate": quote.turnover_rate,
                        "volume": quote.volume,
                        "amount": quote.amount,
                    },
                    by_vt=by_vt,
                    by_symbol=by_symbol,
                )
        except Exception:
            pass

    result: dict[str, dict[str, Any]] = {}
    for vt_symbol in candidates:
        if vt_symbol in by_vt:
            result[vt_symbol] = by_vt[vt_symbol]
        else:
            item = parse_stock_symbol(vt_symbol)
            result[vt_symbol] = {
                "vt_symbol": vt_symbol,
                "symbol": item.symbol if item else vt_symbol.split(".")[0],
            }
    return result


def _intraday_score(
    row: QuoteRowLike,
    *,
    transition: str | None = None,
    pool_median_change: float | None = None,
) -> float:
    merged = merge_row_quotes(row)
    change = float(merged.get("change_pct") or 0)
    change_abs = abs(change)
    volume_ratio = float(merged.get("volume_ratio") or 0)
    amount = float(merged.get("amount") or 0)
    turnover = float(merged.get("turnover_rate") or 0)
    score = change_abs * 10.0
    if pool_median_change is not None and change > pool_median_change + 1.0:
        score += (change - pool_median_change) * 6.0
    if volume_ratio >= 1.2:
        score += min(volume_ratio, 5.0) * 4.0
    if amount > 0:
        score += min(amount / 1_000_000_000, 5.0) * 2.0
    if turnover >= 3.0:
        score += min(turnover, 15.0)
    if transition:
        score += SIGNAL_TRANSITION_BOOST
    score += moneyflow_score_boost(row)
    return score


def _watchlist_metric(
    row: QuoteRowLike,
    *,
    transition: str | None = None,
) -> tuple[str, str, str, str]:
    if transition:
        merged = merge_row_quotes(row)
        change = float(merged.get("change_pct") or 0)
        return "信号跃迁", transition, "涨幅", format_pct(change)

    mf = watchlist_moneyflow_metric(row)
    if mf is not None:
        return mf

    merged = merge_row_quotes(row)
    change = float(merged.get("change_pct") or 0)
    volume_ratio = float(merged.get("volume_ratio") or 0)
    amount = float(merged.get("amount") or 0)
    turnover = float(merged.get("turnover_rate") or 0)
    if abs(change) >= 2.0:
        return "涨幅", format_pct(change), "量比", f"{volume_ratio:.2f}" if volume_ratio > 0 else "—"
    if volume_ratio >= 1.3:
        return "量比", f"{volume_ratio:.2f}", "涨幅", format_pct(change)
    if amount > 0:
        return "成交额", format_amount(amount), "涨幅", format_pct(change)
    return "换手", f"{turnover:.2f}%" if turnover > 0 else "—", "涨幅", format_pct(change)


def _compute_scenario_hints(
    vt_symbols: list[str],
    *,
    config: WatchlistSignalConfig | None = None,
) -> dict[str, str]:
    """为 Top N 异动标的计算轻量 5 日统计情景（非价格预测）。"""
    if not vt_symbols:
        return {}
    cfg = (config or load_watchlist_signal_config()).normalized()
    snapshots: dict[str, SignalSnapshot] = {}
    for vt_symbol in vt_symbols:
        snapshot = build_signal_snapshot(vt_symbol, config=cfg)
        if snapshot is not None:
            snapshots[vt_symbol] = snapshot
    if not snapshots:
        return {}
    metrics_list = batch_build_scenario_metrics(list(snapshots.keys()), snapshots)
    hints: dict[str, str] = {}
    for metrics in metrics_list:
        hint = classify_scenario_hint(metrics)
        if hint:
            hints[metrics.snapshot.vt_symbol] = hint
    return hints


def _row_from_quote(
    vt_symbol: str,
    row: QuoteRowLike,
    *,
    name_map: dict[str, str],
    transition: str | None = None,
    scenario_hint: str | None = None,
) -> RadarRow | None:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return None
    merged = merge_row_quotes(row)
    name = str(merged.get("name") or name_map.get(vt_symbol) or item.name or vt_symbol)
    price_raw = merged.get("last_price") or merged.get("close")
    price = float(price_raw) if isinstance(price_raw, (int, float)) and float(price_raw) > 0 else None
    change_raw = merged.get("change_pct")
    change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
    metric_label, metric_value, sub_label, sub_value = _watchlist_metric(merged, transition=transition)
    if scenario_hint:
        sub_label = "5日情景"
        sub_value = scenario_hint
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=item.symbol,
        price=price,
        change_pct=change_pct,
        metric_label=metric_label,
        metric_value=metric_value,
        sub_label=sub_label,
        sub_value=sub_value,
    )


def _has_quote_data(row: QuoteRowLike) -> bool:
    merged = merge_row_quotes(row)
    return bool(
        merged.get("change_pct") not in (None, "") or float(merged.get("last_price") or merged.get("close") or 0) > 0 or float(merged.get("amount") or 0) > 0
    )


def _score_candidates(
    candidates: list[str],
    quotes_by_vt: dict[str, dict[str, Any]],
    transitions: dict[str, str],
    *,
    anomaly_only: bool,
) -> list[tuple[str, dict[str, Any], float, str | None]]:
    changes = [float(merge_row_quotes(quotes_by_vt.get(vt, {})).get("change_pct") or 0) for vt in candidates if quotes_by_vt.get(vt)]
    pool_median = sorted(changes)[len(changes) // 2] if changes else 0.0

    scored: list[tuple[str, dict[str, Any], float, str | None]] = []
    for vt_symbol in candidates:
        row = quotes_by_vt.get(vt_symbol, {"vt_symbol": vt_symbol})
        transition = transitions.get(vt_symbol)
        score = _intraday_score(row, transition=transition, pool_median_change=pool_median)
        merged = merge_row_quotes(row)
        change = abs(float(merged.get("change_pct") or 0))
        rel_change = float(merged.get("change_pct") or 0) - pool_median
        volume_ratio = float(merged.get("volume_ratio") or 0)
        if transition:
            scored.append((vt_symbol, row, score, transition))
            continue
        if not anomaly_only:
            scored.append((vt_symbol, row, score, None))
            continue
        if change < 1.5 and volume_ratio < 1.2 and score < 8.0 and rel_change < 1.0:
            net_mf = float(merge_row_quotes(row).get("net_mf_amount") or 0)
            if net_mf <= 0:
                continue
        scored.append((vt_symbol, row, score, None))
    scored.sort(key=lambda item: item[2], reverse=True)
    return scored


def load_watchlist_intraday(spec: RadarCardSpec) -> RadarCardData:
    candidates = collect_personal_vt_symbols()
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
    try:
        transitions = compute_signal_transitions(candidates, config=config, max_compute=12)
    except Exception:
        transitions = {}

    quotes_by_vt = _quotes_for_candidates(candidates)
    quotes_by_vt = enrich_quotes_with_moneyflow(quotes_by_vt)
    name_map = name_map_for_symbols(candidates)
    has_any_quote = any(_has_quote_data(row) for row in quotes_by_vt.values())

    scored = _score_candidates(candidates, quotes_by_vt, transitions, anomaly_only=True)
    fallback = False
    if not scored:
        scored = _score_candidates(candidates, quotes_by_vt, transitions, anomaly_only=False)
        fallback = bool(scored)

    top_scored = scored[: spec.top_n]
    scenario_hints: dict[str, str] = {}
    try:
        scenario_hints = _compute_scenario_hints(
            [vt_symbol for vt_symbol, _row, _score, _transition in top_scored],
            config=config,
        )
    except Exception:
        scenario_hints = {}

    rows: list[RadarRow] = []
    transition_count = 0
    scenario_count = 0
    for vt_symbol, row, _score, transition in top_scored:
        parsed = _row_from_quote(
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
        scenario_sample = "、".join(f"{name_map.get(vt, vt)} {hint}" for vt, hint in list(scenario_hints.items())[:3])
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
