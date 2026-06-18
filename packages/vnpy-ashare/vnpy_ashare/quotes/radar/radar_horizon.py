"""雷达页：未来·展望 loader（全市场策略窗口 + 事件日历）。"""

from __future__ import annotations

from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.quotes.radar.outlook_strategy_prefs import (
    load_outlook_signal_config,
    outlook_signal_recent_days,
    outlook_strategy_label,
)
from vnpy_ashare.quotes.radar.radar_ai_cache import resolve_ai_hint, rows_fingerprint
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_cross_refs import build_outlook_cross_ref_hint, build_outlook_cross_ref_suffix
from vnpy_ashare.quotes.radar.radar_horizon_cache import (
    build_horizon_subtitle,
    get_horizon_cache,
)
from vnpy_ashare.quotes.radar.radar_horizon_scan import (
    cache_entry_from_scan,
    collect_daily_k_ready_vt_symbols,
    horizon_empty_message,
    scan_horizon_variant,
)
from vnpy_ashare.quotes.radar.radar_horizon_scenario import SCENARIO_VARIANT_LABELS, SCENARIO_VARIANTS
from vnpy_ashare.quotes.radar.radar_horizon_stats import HorizonScanStats
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, enrich_radar_rows

OUTLOOK_CARD_VARIANTS: dict[str, str] = {
    "outlook_watch": "watch_next",
    "outlook_hold": "hold_next",
}

OUTLOOK_FORCE_RECOMPUTE_CARD_IDS: frozenset[str] = frozenset(
    list(OUTLOOK_CARD_VARIANTS.keys()) + ["outlook_scenario", "outlook_predict"],
)


def build_outlook_digest(rows: tuple[RadarRow, ...], *, variant: str) -> str:
    """结构化摘要（供副标题与本地缓存）。"""
    if not rows:
        return ""
    if variant in SCENARIO_VARIANTS:
        label = SCENARIO_VARIANT_LABELS.get(variant, "情景")
        parts = [f"{label} {len(rows)} 只"]
        band = sum(1 for row in rows if row.sub_label == "参考带")
        if band:
            parts.append(f"有参考带 {band}")
        return "摘要：" + " · ".join(parts)
    buy = sum(1 for row in rows if row.metric_label == "买入")
    hold = sum(1 for row in rows if row.metric_label == "观望")
    scenarios = sum(1 for row in rows if row.sub_label == "5日情景")
    mode = "关注" if variant == "watch_next" else "可持"
    parts = [f"{mode} {len(rows)} 只"]
    if buy:
        parts.append(f"买入 {buy}")
    if hold:
        parts.append(f"观望 {hold}")
    if scenarios:
        parts.append(f"有情景 {scenarios}")
    return "摘要：" + " · ".join(parts)


def _empty_horizon_card(
    spec: RadarCardSpec,
    *,
    subtitle: str,
    empty_message: str,
    scanned_total: int = 0,
) -> RadarCardData:
    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=(),
        empty_message=empty_message,
        updated_at=format_china_datetime_minute(),
        total_count=scanned_total,
    )


def load_outlook_horizon(
    spec: RadarCardSpec,
    *,
    variant: str | None = None,
    force_recompute: bool = False,
) -> RadarCardData:
    resolved_variant = variant or OUTLOOK_CARD_VARIANTS.get(spec.id, "watch_next")
    config = load_outlook_signal_config()
    strategy_key = config.cache_key()
    strategy_label = outlook_strategy_label(config.class_name)
    recent_days = outlook_signal_recent_days(config.class_name)
    scenario_mode = resolved_variant in SCENARIO_VARIANTS
    idle_subtitle = (
        f"约 {recent_days} 日统计情景 · 策略 {strategy_label} · 非目标价" if scenario_mode else f"约 {recent_days} 日窗口 · 策略 {strategy_label} · 非价格预测"
    )

    if not force_recompute:
        cached = get_horizon_cache(resolved_variant, strategy_key=strategy_key)
        if cached is not None:
            subtitle = build_horizon_subtitle(
                cached,
                signal_recent_days=recent_days,
                strategy_label=strategy_label,
            )
            if scenario_mode:
                subtitle = f"{subtitle} · 统计情景非目标价"
            rows = enrich_radar_rows(cached.rows)
            cross_suffix = build_outlook_cross_ref_suffix(rows)
            if cross_suffix:
                subtitle = f"{subtitle} · {cross_suffix}"
            cross_hint = build_outlook_cross_ref_hint(rows)
            if not rows:
                stats = HorizonScanStats(
                    scanned_total=cached.scanned_total,
                    excluded_count=cached.excluded_count,
                    prefilter_total=cached.prefilter_total,
                    refined_total=cached.refined_total,
                    kline_missing=cached.kline_missing,
                )
                return _empty_horizon_card(
                    spec,
                    subtitle=subtitle,
                    empty_message=horizon_empty_message(stats, card_title=spec.title),
                    scanned_total=cached.scanned_total,
                )
            return RadarCardData(
                card_id=spec.id,
                title=spec.title,
                subtitle=subtitle,
                rows=rows,
                empty_message="",
                updated_at=cached.computed_at,
                total_count=len(rows),
                ai_hint=resolve_ai_hint(
                    spec.id,
                    variant=resolved_variant if scenario_mode else "",
                    fingerprint=rows_fingerprint(rows),
                    digest=build_outlook_digest(rows, variant=resolved_variant),
                )
                + (f" · {cross_hint}" if cross_hint else ""),
            )
        return _empty_horizon_card(
            spec,
            subtitle=idle_subtitle,
            empty_message=(
                "暂无展望快照，请点击卡片刷新或于定时任务中运行「雷达展望扫描」。"
                if collect_daily_k_ready_vt_symbols()
                else "本地暂无日 K 数据，请先运行「全市场日 K」后再刷新展望卡。"
            ),
        )

    scan_result = scan_horizon_variant(resolved_variant, top_n=spec.top_n, config=config)

    cached_after = get_horizon_cache(resolved_variant, strategy_key=strategy_key)
    subtitle = build_horizon_subtitle(
        cached_after or cache_entry_from_scan(scan_result),
        signal_recent_days=recent_days,
        strategy_label=strategy_label,
    )
    if scenario_mode:
        subtitle = f"{subtitle} · 统计情景非目标价"
    rows = enrich_radar_rows(scan_result.rows)
    cross_suffix = build_outlook_cross_ref_suffix(rows)
    if cross_suffix:
        subtitle = f"{subtitle} · {cross_suffix}"
    cross_hint = build_outlook_cross_ref_hint(rows)
    stats = scan_result.stats

    if not rows:
        return _empty_horizon_card(
            spec,
            subtitle=subtitle,
            empty_message=horizon_empty_message(stats, card_title=spec.title),
            scanned_total=stats.scanned_total,
        )

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=rows,
        empty_message="",
        updated_at=scan_result.computed_at,
        total_count=len(rows),
        ai_hint=resolve_ai_hint(
            spec.id,
            variant=resolved_variant if scenario_mode else "",
            fingerprint=rows_fingerprint(rows),
            digest=build_outlook_digest(rows, variant=resolved_variant),
        )
        + (f" · {cross_hint}" if cross_hint else ""),
    )


def build_outlook_ai_prompt(payload: dict[str, RadarCardData], *, card_id: str) -> str:
    """生成未来展望卡 AI 解读预填文案。"""
    data = payload.get(card_id)
    if data is None or not data.rows:
        return ""
    if card_id == "outlook_scenario":
        label = data.rows[0].metric_label if data.rows else "情景"
        lines = [
            f"请基于以下雷达「未来·情景（{label}）」快照，做走势情景解读：",
            "1. 说明统计参考带与动能含义（约 5 个交易日，非确定性预测）",
            "2. 逐只解读偏多/偏空/波动特征与结构锚点",
            "3. 给出不宜追涨/不宜杀跌的情形",
            "4. 不得给出目标价或未在数据中的预测",
            "",
            data.subtitle,
            "",
        ]
        for row in data.rows:
            lines.append(f"- {row.name}({row.symbol}) {row.metric_label} {row.metric_value} · {row.sub_label} {row.sub_value}")
        return "\n".join(lines)
    variant = OUTLOOK_CARD_VARIANTS.get(card_id, "watch_next")
    mode = "未来几日关注" if variant == "watch_next" else "未来几日可持仓"
    lines = [
        f"请基于以下雷达「{mode}」快照，给出关注理由与风险提示：",
        "1. 说明策略信号窗口含义（约 5 个交易日，非涨跌预测）",
        "2. 逐只解读信号、强度、距买点与 5 日统计情景",
        "3. 给出不宜关注/不宜持有的情形",
        "4. 不得给出目标价或未在数据中的预测",
        "",
        data.subtitle,
        "",
    ]
    for row in data.rows:
        lines.append(f"- {row.name}({row.symbol}) {row.metric_label} 强度{row.metric_value} · {row.sub_label} {row.sub_value}")
    return "\n".join(lines)
