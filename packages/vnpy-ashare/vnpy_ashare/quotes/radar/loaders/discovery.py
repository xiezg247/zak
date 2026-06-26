"""发现类雷达卡片（放量、主力资金）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.core.numbers import float_or_none
from vnpy_ashare.domain.screener.result_row import screening_row_to_dict
from vnpy_ashare.quotes.format import format_pct
from vnpy_ashare.quotes.radar.loaders.rows import (
    discovery_pool_size,
    liquidity_metric,
    moneyflow_metric,
    radar_source_payload,
    row_from_dict,
)
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, merge_row_quotes
from vnpy_ashare.quotes.radar.radar_pool import name_map_for_symbols
from vnpy_ashare.quotes.radar.loaders.scheduled_intraday import (
    peek_fresh_intraday_screen_run,
    volume_hits_from_intraday_run,
)
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.dimensions.base import DimensionHit, dimension_hit_row, rank_score
from vnpy_ashare.screener.dimensions.moneyflow_resolve import (
    build_moneyflow_source_subtitle,
    resolve_moneyflow_hits,
)
from vnpy_ashare.screener.dimensions.volume_dedup import build_volume_discovery_subtitle
from vnpy_ashare.screener.dimensions.volume_ratio import run_volume_ratio
from vnpy_ashare.screener.dimensions.volume_surge import run_volume_surge
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.preset.rules import _quote_liquidity_key


def discovery_hits_card(
    spec: RadarCardSpec,
    hits,
    total: int,
    *,
    metric_builder,
    empty_no_data: str,
) -> RadarCardData:
    if not hits:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=f"扫描 {total} 只" if total else "",
            rows=(),
            empty_message=empty_no_data,
            updated_at="",
        )
    rows: list[RadarRow] = []
    vt_symbols = [str(hit.row.get("vt_symbol") or "").strip() for hit in hits]
    batch_name_map = name_map_for_symbols([vt for vt in vt_symbols if vt])

    filter_inputs: list[dict[str, Any]] = []
    for hit in hits:
        row = screening_row_to_dict(hit.row)
        vt = str(row.get("vt_symbol") or "").strip()
        mapped_name = str(batch_name_map.get(vt) or row.get("name") or "").strip()
        if mapped_name:
            row["name"] = mapped_name
        filter_inputs.append(row)
    filtered_rows = apply_recipe_filters(filter_inputs)
    allowed_vt = {str(row.get("vt_symbol") or "") for row in filtered_rows}
    for hit in hits:
        vt = str(hit.row.get("vt_symbol") or "").strip()
        if vt not in allowed_vt:
            continue
        parsed = row_from_dict(hit.row, name_map=batch_name_map)
        if parsed is None:
            continue
        metric_label, metric_value, sub_label, sub_value = metric_builder(radar_source_payload(hit.row), hit)
        rows.append(
            RadarRow(
                vt_symbol=parsed.vt_symbol,
                name=parsed.name,
                symbol=parsed.symbol,
                price=parsed.price,
                change_pct=parsed.change_pct,
                metric_label=metric_label,
                metric_value=metric_value,
                sub_label=sub_label,
                sub_value=sub_value,
            )
        )
        if len(rows) >= spec.top_n:
            break
    if not rows:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=f"扫描 {total} 只" if total else "",
            rows=(),
            empty_message=empty_no_data,
            updated_at="",
        )
    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=f"全市场 Top {len(rows)}" + (f" / {total}" if total else ""),
        rows=tuple(rows),
        empty_message="",
        updated_at="",
        total_count=len(rows),
    )


def volume_surge_needs_ratio_fallback(hits) -> bool:
    if not hits:
        return False
    return all(float(merge_row_quotes(hit.row).get("volume") or 0) <= 0 and float(merge_row_quotes(hit.row).get("amount") or 0) <= 0 for hit in hits)


def volume_liquidity_proxy(pool_size: int, total: int):
    """成交量/量比均不可用时的成交额/换手代理排行。"""
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], total

    ranked = sorted(apply_recipe_filters(snapshot.rows), key=_quote_liquidity_key, reverse=True)
    hits: list[DimensionHit] = []
    for index, row in enumerate(ranked[:pool_size], start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="volume_surge",
                label="放量",
                weight=1.0,
                score=rank_score(index, min(len(ranked), pool_size)),
                reason=f"放量：流动性代理，排名第 {index}",
                row=dimension_hit_row(row),
            )
        )
    return hits, snapshot.total


def load_discovery_volume_surge(spec: RadarCardSpec) -> RadarCardData:
    pool_size = discovery_pool_size(spec.top_n)
    intraday_run = peek_fresh_intraday_screen_run()
    if intraday_run is not None:
        hits, total = volume_hits_from_intraday_run(intraday_run, pool_size)
        if hits:
            def _volume_metric(row: dict[str, Any], hit) -> tuple[str, str, str, str]:
                if hit.dimension_id == "volume_ratio":
                    merged = merge_row_quotes(row)
                    ratio = float(merged.get("volume_ratio") or row.get("volume_ratio") or 0)
                    change = float_or_none(merged.get("change_pct"))
                    return "量比", f"{ratio:.2f}", "涨幅", format_pct(change)
                return liquidity_metric(row)

            subtitle_suffix = build_volume_discovery_subtitle(hits)
            data = discovery_hits_card(
                spec,
                hits,
                total,
                metric_builder=_volume_metric,
                empty_no_data="暂无行情数据，请先采集行情或打开「市场」页。",
            )
            if data.rows:
                subtitle = data.subtitle + subtitle_suffix if subtitle_suffix else data.subtitle
                subtitle = f"定时快照 · {subtitle}" if subtitle else "定时快照"
                return RadarCardData(
                    card_id=data.card_id,
                    title=data.title,
                    subtitle=subtitle,
                    rows=data.rows,
                    empty_message=data.empty_message,
                    updated_at=intraday_run.created_at,
                    run_id=intraday_run.id,
                    detail_page_key="auto_screener",
                    total_count=data.total_count,
                    ai_hint=data.ai_hint,
                    sector_names=data.sector_names,
                )

    hits, total = run_volume_surge(pool_size, weight=1.0)

    if volume_surge_needs_ratio_fallback(hits):
        ratio_hits, ratio_total = run_volume_ratio(pool_size, weight=1.0)
        if ratio_hits:
            hits, total = ratio_hits, ratio_total
        # 量比无数据时保留放量原结果，避免把有效行情行清空

    if not hits and total > 0:
        hits, total = volume_liquidity_proxy(pool_size, total)

    def _volume_metric(row: dict[str, Any], hit) -> tuple[str, str, str, str]:
        if hit.dimension_id == "volume_ratio":
            merged = merge_row_quotes(row)
            ratio = float(merged.get("volume_ratio") or row.get("volume_ratio") or 0)
            change = float_or_none(merged.get("change_pct"))
            return "量比", f"{ratio:.2f}", "涨幅", format_pct(change)
        return liquidity_metric(row)

    subtitle_suffix = build_volume_discovery_subtitle(hits)
    data = discovery_hits_card(
        spec,
        hits,
        total,
        metric_builder=_volume_metric,
        empty_no_data="暂无行情数据，请先采集行情或打开「市场」页。",
    )
    if data.rows and subtitle_suffix:
        return RadarCardData(
            card_id=data.card_id,
            title=data.title,
            subtitle=data.subtitle + subtitle_suffix,
            rows=data.rows,
            empty_message=data.empty_message,
            updated_at=data.updated_at,
            run_id=data.run_id,
            detail_page_key=data.detail_page_key,
            total_count=data.total_count,
            ai_hint=data.ai_hint,
            sector_names=data.sector_names,
        )
    return data


def load_discovery_moneyflow_intraday(spec: RadarCardSpec) -> RadarCardData:
    pool_size = discovery_pool_size(spec.top_n)

    hits, total, trade_date = resolve_moneyflow_hits(pool_size, weight=1.0, enrich_kind=True)
    subtitle_suffix = build_moneyflow_source_subtitle(hits, trade_date)

    data = discovery_hits_card(
        spec,
        hits,
        total,
        metric_builder=moneyflow_metric,
        empty_no_data="暂无行情数据，请先运行「主力资金预拉」或打开「市场」页。",
    )
    if data.rows and subtitle_suffix:
        return RadarCardData(
            card_id=data.card_id,
            title=data.title,
            subtitle=data.subtitle + subtitle_suffix,
            rows=data.rows,
            empty_message=data.empty_message,
            updated_at=data.updated_at,
            run_id=data.run_id,
            detail_page_key=data.detail_page_key,
            total_count=data.total_count,
            ai_hint=data.ai_hint,
            sector_names=data.sector_names,
        )
    return data
