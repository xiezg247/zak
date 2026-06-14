"""雷达页卡片数据加载（纯函数，Worker 线程调用）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.radar_catalog import (
    DEFAULT_SCENARIO_VARIANT,
    DEFAULT_SCREEN_TASK_VARIANT,
    DEFAULT_SECTOR_VARIANT,
    RADAR_CARD_BY_ID,
    RADAR_CARD_SPECS,
    RadarCardSpec,
)
from vnpy_ashare.quotes.radar_models import (
    RadarCardData,
    RadarResonanceEntry,
    RadarRow,
    float_or_none,
    format_pct,
    merge_row_quotes,
    quote_map,
)
from vnpy_ashare.quotes.radar_pool import name_map_for_symbols
from vnpy_ashare.quotes.radar_sector import load_sector_theme
from vnpy_ashare.quotes.radar_watchlist import load_watchlist_intraday
from vnpy_ashare.screener.dimensions.volume_ratio import run_volume_ratio
from vnpy_ashare.screener.dimensions.volume_surge import run_volume_surge
from vnpy_ashare.screener.run.run_store import get_latest_run, is_auto_run, is_strategy_run, list_runs

# 兼容旧 import 路径
_quote_map = quote_map
_float_or_none = float_or_none
_format_pct = format_pct
_merge_row_quotes = merge_row_quotes


def _discovery_pool_size(top_n: int) -> int:
    """发现卡多取候选，硬过滤 ST 后仍能凑满 top_n。"""
    return min(max(top_n * 5, top_n + 12), 80)


def _is_discovery_st_excluded(row: dict[str, Any], name_map: dict[str, str]) -> bool:
    """已废弃：请使用 apply_screening_filters。保留兼容测试 import。"""
    from vnpy_ashare.screener.hard_filters import apply_screening_filters

    return not apply_screening_filters([row])


def _screener_metric(row: dict[str, Any]) -> tuple[str, str, str, str]:
    if "composite_score" in row:
        score = _float_or_none(row.get("composite_score"))
        return "综合分", f"{score:.1f}" if score is not None else "—", "涨幅", _format_pct(_float_or_none(row.get("change_pct")))
    change = _float_or_none(row.get("change_pct") or row.get("pct_chg"))
    turnover = _float_or_none(row.get("turnover_rate"))
    return "涨幅", _format_pct(change), "换手", f"{turnover:.2f}%" if turnover is not None else "—"


def _liquidity_metric(row: dict[str, Any]) -> tuple[str, str, str, str]:
    from vnpy_ashare.ui.quotes.table.columns import format_amount, format_volume

    merged = _merge_row_quotes(row)
    volume = float(merged.get("volume") or 0)
    amount = float(merged.get("amount") or 0)
    volume_ratio = float(merged.get("volume_ratio") or 0)
    change = _float_or_none(merged.get("change_pct"))
    turnover = _float_or_none(merged.get("turnover_rate"))
    if volume > 0:
        return "成交量", format_volume(volume), "涨幅", _format_pct(change)
    if amount > 0:
        return "成交额", format_amount(amount), "涨幅", _format_pct(change)
    if volume_ratio > 0:
        return "量比", f"{volume_ratio:.2f}", "涨幅", _format_pct(change)
    return "涨幅", _format_pct(change), "换手", f"{turnover:.2f}%" if turnover is not None else "—"


def _moneyflow_metric(row: dict[str, Any], _hit=None) -> tuple[str, str, str, str]:
    from vnpy_ashare.quotes.moneyflow_kind import classify_moneyflow_row, flow_kind_label
    from vnpy_ashare.ui.quotes.table.columns import format_amount

    merged = _merge_row_quotes(row)
    kind = classify_moneyflow_row(merged)
    kind_label = flow_kind_label(kind)
    net_mf = _float_or_none(merged.get("net_mf_amount"))
    change = _float_or_none(merged.get("change_pct"))

    if kind == "proxy":
        amount = float(merged.get("amount") or 0)
        if amount > 0:
            return "成交额", format_amount(amount), kind_label, _format_pct(change)
        turnover = _float_or_none(merged.get("turnover_rate"))
        return "涨幅", _format_pct(change), kind_label, f"{turnover:.2f}%" if turnover is not None else "—"

    if net_mf is not None and net_mf != 0:
        return "主力净流入", f"{net_mf:,.0f} 万", kind_label, _format_pct(change)
    amount = float(merged.get("amount") or 0)
    if amount > 0:
        return "成交额", format_amount(amount), kind_label, _format_pct(change)
    turnover = _float_or_none(merged.get("turnover_rate"))
    return "涨幅", _format_pct(change), kind_label, f"{turnover:.2f}%" if turnover is not None else "—"


def _looks_like_vt_symbol(text: str) -> bool:
    if "." not in text:
        return False
    _code, suffix = text.rsplit(".", 1)
    return suffix.upper() in {"SSE", "SZSE", "BSE", "SH", "SZ", "BJ"}


def _resolve_row_display_name(
    vt_symbol: str,
    row: dict[str, Any],
    merged: dict[str, Any],
    *,
    item,
    name_map: dict[str, str],
) -> str:
    for candidate in (
        str(merged.get("name") or "").strip(),
        str(row.get("name") or "").strip(),
        str(name_map.get(vt_symbol) or "").strip(),
        (item.name if item else "").strip(),
    ):
        if candidate and candidate != vt_symbol and not _looks_like_vt_symbol(candidate):
            return candidate
    if item is not None:
        return item.symbol
    return vt_symbol.split(".")[0]


def _row_from_dict(row: dict[str, Any], *, name_map: dict[str, str] | None = None) -> RadarRow | None:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return None
    item = parse_stock_symbol(vt_symbol)
    merged = _merge_row_quotes(row)
    lookup = name_map or {}
    name = _resolve_row_display_name(vt_symbol, row, merged, item=item, name_map=lookup)
    symbol = str(row.get("symbol") or (item.symbol if item else vt_symbol.split(".")[0]))
    price = _float_or_none(merged.get("last_price") or merged.get("close"))
    change_pct = _float_or_none(merged.get("change_pct") or row.get("change_pct") or row.get("pct_chg"))
    metric_label, metric_value, sub_label, sub_value = _screener_metric(merged)
    rs_sub = _relative_strength_subline(merged)
    if rs_sub is not None:
        sub_label, sub_value = rs_sub
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=symbol,
        price=price,
        change_pct=change_pct,
        metric_label=metric_label,
        metric_value=metric_value,
        sub_label=sub_label,
        sub_value=sub_value,
    )


def _relative_strength_subline(row: dict[str, Any]) -> tuple[str, str] | None:
    from vnpy_ashare.quotes.radar_relative_strength import build_relative_strength_subline

    return build_relative_strength_subline(row)


def _rows_from_screener(rows: list[dict[str, Any]], *, top_n: int) -> tuple[RadarRow, ...]:
    batch = rows[:top_n]
    vt_symbols = [str(row.get("vt_symbol") or "").strip() for row in batch]
    name_map = name_map_for_symbols([vt for vt in vt_symbols if vt])
    result: list[RadarRow] = []
    for row in batch:
        parsed = _row_from_dict(row, name_map=name_map)
        if parsed is not None:
            result.append(parsed)
    return tuple(result)


def _detail_page_key_for_run(record) -> str:
    if is_strategy_run(record.config):
        return "screener"
    return "auto_screener"


def _run_subtitle(record) -> str:
    summary = str(record.config.get("reason_summary") or record.condition or "").strip()
    parts: list[str] = []
    if record.row_count:
        parts.append(f"共 {record.row_count} 只")
    if summary:
        parts.append(summary)
    return " · ".join(parts)


def _card_from_run(
    spec: RadarCardSpec,
    record,
    *,
    empty_message: str,
) -> RadarCardData:
    if record is None or not record.rows:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="",
            rows=(),
            empty_message=empty_message,
            updated_at="",
        )
    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=_run_subtitle(record),
        rows=_rows_from_screener(record.rows, top_n=spec.top_n),
        empty_message="",
        updated_at=record.created_at,
        run_id=record.id,
        detail_page_key=_detail_page_key_for_run(record),
        total_count=record.row_count,
    )


def _find_run_for_task_variant(variant: str):
    if variant == "strategy":
        for record in list_runs(limit=30):
            if is_strategy_run(record.config):
                return record
        return None
    trigger = f"scheduled_{variant.removeprefix('scheduled_')}"
    for record in list_runs(limit=30):
        if not is_auto_run(record.config):
            continue
        if str(record.config.get("trigger", "")) == trigger:
            return record
    return None


def load_screen_latest(spec: RadarCardSpec) -> RadarCardData:
    return _card_from_run(
        spec,
        get_latest_run(),
        empty_message="暂无选股记录，请前往「策略选股」或「自动选股」运行。",
    )


def load_screen_task(spec: RadarCardSpec, *, variant: str = DEFAULT_SCREEN_TASK_VARIANT) -> RadarCardData:
    record = _find_run_for_task_variant(variant)
    label = {
        "scheduled_intraday": "盘中定时任务",
        "scheduled_post_close": "盘后定时任务",
        "strategy": "策略选股",
    }.get(variant, variant)
    empty = f"暂无「{label}」运行记录。"
    return _card_from_run(spec, record, empty_message=empty)


def _discovery_hits_card(
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
    name_map = name_map_for_symbols([vt for vt in vt_symbols if vt])
    from vnpy_ashare.screener.hard_filters import apply_screening_filters

    filter_inputs: list[dict[str, Any]] = []
    for hit in hits:
        row = dict(hit.row)
        vt = str(row.get("vt_symbol") or "").strip()
        mapped_name = str(name_map.get(vt) or row.get("name") or "").strip()
        if mapped_name:
            row["name"] = mapped_name
        filter_inputs.append(row)
    filtered_rows = apply_screening_filters(filter_inputs)
    allowed_vt = {str(row.get("vt_symbol") or "") for row in filtered_rows}
    for hit in hits:
        vt = str(hit.row.get("vt_symbol") or "").strip()
        if vt not in allowed_vt:
            continue
        row = hit.row
        parsed = _row_from_dict(row, name_map=name_map)
        if parsed is None:
            continue
        metric_label, metric_value, sub_label, sub_value = metric_builder(row, hit)
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


def _volume_surge_needs_ratio_fallback(hits) -> bool:
    if not hits:
        return False
    return all(float(_merge_row_quotes(hit.row).get("volume") or 0) <= 0 and float(_merge_row_quotes(hit.row).get("amount") or 0) <= 0 for hit in hits)


def _volume_liquidity_proxy(pool_size: int, total: int):
    """成交量/量比均不可用时的成交额/换手代理排行。"""
    from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
    from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
    from vnpy_ashare.screener.dimensions.base import DimensionHit, rank_score
    from vnpy_ashare.screener.hard_filters import apply_screening_filters
    from vnpy_ashare.screener.preset.rules import _quote_liquidity_key

    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return [], total

    ranked = sorted(apply_screening_filters(snapshot.rows), key=_quote_liquidity_key, reverse=True)
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
                row=dict(row),
            )
        )
    return hits, snapshot.total


def load_discovery_volume_surge(spec: RadarCardSpec) -> RadarCardData:
    pool_size = _discovery_pool_size(spec.top_n)
    hits, total = run_volume_surge(pool_size, weight=1.0)

    if _volume_surge_needs_ratio_fallback(hits):
        ratio_hits, ratio_total = run_volume_ratio(pool_size, weight=1.0)
        if ratio_hits:
            hits, total = ratio_hits, ratio_total
        # 量比无数据时保留放量原结果，避免把有效行情行清空

    if not hits and total > 0:
        hits, total = _volume_liquidity_proxy(pool_size, total)

    def _volume_metric(row: dict[str, Any], hit) -> tuple[str, str, str, str]:
        if hit.dimension_id == "volume_ratio":
            merged = _merge_row_quotes(row)
            ratio = float(merged.get("volume_ratio") or row.get("volume_ratio") or 0)
            change = _float_or_none(merged.get("change_pct"))
            return "量比", f"{ratio:.2f}", "涨幅", _format_pct(change)
        return _liquidity_metric(row)

    return _discovery_hits_card(
        spec,
        hits,
        total,
        metric_builder=_volume_metric,
        empty_no_data="暂无行情数据，请先采集行情或打开「市场」页。",
    )


def load_discovery_moneyflow_intraday(spec: RadarCardSpec) -> RadarCardData:
    pool_size = _discovery_pool_size(spec.top_n)
    from vnpy_ashare.screener.dimensions.moneyflow_resolve import (
        build_moneyflow_source_subtitle,
        resolve_moneyflow_hits,
    )

    hits, total, trade_date = resolve_moneyflow_hits(pool_size, weight=1.0, enrich_kind=True)
    subtitle_suffix = build_moneyflow_source_subtitle(hits, trade_date)

    data = _discovery_hits_card(
        spec,
        hits,
        total,
        metric_builder=_moneyflow_metric,
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


def incremental_refresh_radar_card_quotes(data: RadarCardData) -> RadarCardData:
    """仅刷新卡片行的现价与涨幅，不重算发现 / 板块等指标。"""
    from dataclasses import replace

    from vnpy_ashare.quotes.radar_models import enrich_radar_rows
    from vnpy_ashare.screener.data.screening_context import preload_screening_context_quotes, screening_context_scope

    if not data.rows:
        return data
    with screening_context_scope() as ctx:
        preload_screening_context_quotes(ctx)
        enriched = enrich_radar_rows(data.rows)
    return replace(data, rows=enriched)


def load_radar_card(
    card_id: str,
    *,
    screen_task_variant: str = DEFAULT_SCREEN_TASK_VARIANT,
    sector_variant: str = DEFAULT_SECTOR_VARIANT,
    scenario_variant: str = DEFAULT_SCENARIO_VARIANT,
    force_recompute: bool = False,
) -> RadarCardData:
    """加载单张雷达卡片；行情类卡片自动复用 ScreeningContext。"""
    if card_id in _RADAR_FULL_CONTEXT_CARD_IDS:
        from vnpy_ashare.screener.data.screening_context import preload_screening_context, screening_context_scope

        with screening_context_scope() as ctx:
            preload_screening_context(ctx)
            return _load_radar_card_uncached(
                card_id,
                screen_task_variant=screen_task_variant,
                sector_variant=sector_variant,
                scenario_variant=scenario_variant,
                force_recompute=force_recompute,
            )
    if card_id in _RADAR_QUOTE_CONTEXT_CARD_IDS:
        from vnpy_ashare.screener.data.screening_context import preload_screening_context_quotes, screening_context_scope

        with screening_context_scope() as ctx:
            preload_screening_context_quotes(ctx)
            return _load_radar_card_uncached(
                card_id,
                screen_task_variant=screen_task_variant,
                sector_variant=sector_variant,
                scenario_variant=scenario_variant,
                force_recompute=force_recompute,
            )
    return _load_radar_card_uncached(
        card_id,
        screen_task_variant=screen_task_variant,
        sector_variant=sector_variant,
        scenario_variant=scenario_variant,
        force_recompute=force_recompute,
    )


_RADAR_FULL_CONTEXT_CARD_IDS = frozenset({
    "discovery_volume_surge",
    "discovery_moneyflow_intraday",
    "watchlist_intraday",
    "sector_theme",
})

_RADAR_QUOTE_CONTEXT_CARD_IDS = frozenset({
    "screen_latest",
    "screen_task",
    "outlook_watch",
    "outlook_hold",
    "outlook_scenario",
})


def _load_radar_card_uncached(
    card_id: str,
    *,
    screen_task_variant: str = DEFAULT_SCREEN_TASK_VARIANT,
    sector_variant: str = DEFAULT_SECTOR_VARIANT,
    scenario_variant: str = DEFAULT_SCENARIO_VARIANT,
    force_recompute: bool = False,
) -> RadarCardData:
    """加载单张雷达卡片（无额外上下文包装）。"""
    spec = RADAR_CARD_BY_ID.get(card_id)
    if spec is None:
        msg = f"未知雷达卡片：{card_id}"
        raise ValueError(msg)
    if spec.id == "screen_latest":
        return load_screen_latest(spec)
    if spec.id == "screen_task":
        return load_screen_task(spec, variant=screen_task_variant)
    if spec.id == "discovery_volume_surge":
        return load_discovery_volume_surge(spec)
    if spec.id == "discovery_moneyflow_intraday":
        return load_discovery_moneyflow_intraday(spec)
    if spec.id == "watchlist_intraday":
        return load_watchlist_intraday(spec)
    if spec.id == "sector_theme":
        return load_sector_theme(spec, variant=sector_variant)
    if spec.id in ("outlook_watch", "outlook_hold"):
        from vnpy_ashare.quotes.radar_horizon import load_outlook_horizon

        return load_outlook_horizon(spec, force_recompute=force_recompute)
    if spec.id == "outlook_scenario":
        from vnpy_ashare.quotes.radar_horizon import load_outlook_horizon

        return load_outlook_horizon(
            spec,
            variant=scenario_variant,
            force_recompute=force_recompute,
        )
    msg = f"未实现的雷达卡片加载器：{card_id}"
    raise ValueError(msg)


def load_radar_board(
    *,
    screen_task_variant: str = DEFAULT_SCREEN_TASK_VARIANT,
    sector_variant: str = DEFAULT_SECTOR_VARIANT,
) -> dict[str, RadarCardData]:
    """加载全部雷达卡片（共享 ScreeningContext + 并行加载）。"""
    import os

    from vnpy_ashare.data.download_concurrency import run_parallel_map
    from vnpy_ashare.screener.data.screening_context import preload_screening_context, screening_context_scope

    raw_workers = os.getenv("RADAR_BOARD_MAX_WORKERS", "4").strip()
    try:
        max_workers = max(1, min(int(raw_workers), 8))
    except ValueError:
        max_workers = 4

    with screening_context_scope() as ctx:
        preload_screening_context(ctx)

        def load_one(spec: RadarCardSpec) -> tuple[str, RadarCardData]:
            return spec.id, load_radar_card(
                spec.id,
                screen_task_variant=screen_task_variant,
                sector_variant=sector_variant,
            )

        pairs = run_parallel_map(
            list(RADAR_CARD_SPECS),
            load_one,
            max_workers=min(max_workers, len(RADAR_CARD_SPECS)),
        )
        return dict(pairs)


def _accumulate_radar_resonance(
    payload: dict[str, RadarCardData],
) -> dict[str, dict[str, object]]:
    from vnpy_ashare.quotes.radar_catalog import radar_card_resonance_weight

    grouped: dict[str, dict[str, object]] = {}
    for data in payload.values():
        card_weight = radar_card_resonance_weight(data.card_id)
        seen_in_card: set[str] = set()
        for row in data.rows:
            if row.vt_symbol in seen_in_card:
                continue
            seen_in_card.add(row.vt_symbol)
            bucket = grouped.setdefault(
                row.vt_symbol,
                {"row": row, "titles": [], "card_count": 0, "weight_score": 0.0},
            )
            titles = bucket["titles"]
            assert isinstance(titles, list)
            titles.append(data.title)
            bucket["card_count"] = int(bucket.get("card_count") or 0) + 1
            bucket["weight_score"] = float(bucket.get("weight_score") or 0.0) + card_weight
            bucket["row"] = row
    return grouped


def build_radar_resonance_list(
    payload: dict[str, RadarCardData],
    *,
    min_cards: int = 2,
) -> tuple[RadarResonanceEntry, ...]:
    """汇总跨卡共振标的，按加权分降序。"""
    grouped = _accumulate_radar_resonance(payload)
    entries: list[RadarResonanceEntry] = []
    for vt_symbol, bucket in grouped.items():
        titles = bucket["titles"]
        assert isinstance(titles, list)
        card_count = int(bucket.get("card_count") or 0)
        if card_count < min_cards:
            continue
        row = bucket["row"]
        assert isinstance(row, RadarRow)
        weight_score = round(float(bucket.get("weight_score") or 0.0), 2)
        entries.append(
            RadarResonanceEntry(
                vt_symbol=vt_symbol,
                name=row.name,
                symbol=row.symbol,
                card_count=card_count,
                card_titles=tuple(titles),
                price=row.price,
                change_pct=row.change_pct,
                resonance_score=weight_score,
            )
        )
    entries.sort(
        key=lambda item: (
            -item.resonance_score,
            -item.card_count,
            item.vt_symbol,
        ),
    )
    return tuple(entries)


def build_radar_resonance_ai_prompt(payload: dict[str, RadarCardData]) -> str:
    """生成仅针对共振标的的 AI 解读预填文案。"""
    entries = build_radar_resonance_list(payload)
    if not entries:
        return ""
    lines = [
        "请重点解读以下雷达共振标的（同时出现在多张卡片）：",
        "1. 共振原因与共性特征",
        "2. 优先关注顺序与风险提示",
        "3. 不要编造未出现在数据中的价格或指标",
        "",
    ]
    for entry in entries:
        price = f"{entry.price:.2f}" if entry.price is not None else "—"
        change = f"{entry.change_pct:+.2f}%" if entry.change_pct is not None else "—"
        cards = "、".join(entry.card_titles)
        score_note = f" · 加权 {entry.resonance_score:.1f}" if entry.resonance_score > 0 else ""
        lines.append(f"- {entry.name}({entry.symbol}) {change} 现价{price} · {entry.card_count}卡{score_note}：{cards}")
    return "\n".join(lines)


def compute_radar_resonance(payload: dict[str, RadarCardData], *, min_cards: int = 2) -> dict[str, int]:
    """统计在多张卡片中出现的标的（共振卡数）。"""
    grouped = _accumulate_radar_resonance(payload)
    return {
        vt_symbol: int(bucket.get("card_count") or 0)
        for vt_symbol, bucket in grouped.items()
        if int(bucket.get("card_count") or 0) >= min_cards
    }


def compute_radar_resonance_scores(
    payload: dict[str, RadarCardData],
    *,
    min_cards: int = 2,
) -> dict[str, float]:
    """共振加权分（发现卡权重高于选股缓存）。"""
    grouped = _accumulate_radar_resonance(payload)
    return {
        vt_symbol: round(float(bucket.get("weight_score") or 0.0), 2)
        for vt_symbol, bucket in grouped.items()
        if int(bucket.get("card_count") or 0) >= min_cards
    }


def _row_ai_summary(row: RadarRow) -> str:
    price = f"{row.price:.2f}" if row.price is not None else "—"
    change = f"{row.change_pct:+.2f}%" if row.change_pct is not None else "—"
    return f"{row.name}({row.symbol}) 现价{price} {change} · {row.metric_label} {row.metric_value} · {row.sub_label} {row.sub_value}"


def build_radar_card_ai_prompt(
    card_id: str,
    data: RadarCardData,
    *,
    resonance_counts: dict[str, int] | None = None,
) -> str:
    """生成单张雷达卡的 AI 解读预填文案。"""
    if not data.rows and not data.empty_message:
        return ""
    counts = resonance_counts or {}
    lines = [
        f"请解读雷达卡片「{data.title}」：",
        "1. 概括本卡核心结论与优先顺序",
        "2. 标注共振标的（若有多卡重复出现）",
        "3. 不要编造未出现在数据中的价格或指标",
        "",
    ]
    if data.subtitle:
        lines.append(data.subtitle)
    if data.ai_hint:
        lines.append(data.ai_hint)
    lines.append("")
    if not data.rows:
        lines.append(data.empty_message or "（暂无数据）")
        return "\n".join(lines).strip()

    if card_id == "watchlist_intraday":
        lines[0] = "请解读雷达「自选·异动」：关注自选池内波动、信号跃迁与 5 日统计情景（非价格预测）。"
    elif card_id == "sector_theme":
        lines[0] = "请解读雷达「板块·主线」：归纳今日行业轮动与龙头特征。"
    elif card_id in ("outlook_watch", "outlook_hold", "outlook_scenario"):
        from vnpy_ashare.quotes.radar_horizon import build_outlook_ai_prompt

        single = build_outlook_ai_prompt({card_id: data}, card_id=card_id)
        return single or "\n".join(lines).strip()

    for row in data.rows:
        marker = "★ " if counts.get(row.vt_symbol, 0) >= 2 else ""
        lines.append(f"- {marker}{_row_ai_summary(row)}")
    return "\n".join(lines).strip()


def build_radar_ai_prompt(
    payload: dict[str, RadarCardData],
) -> str:
    """生成雷达页 AI 洞察预填文案。"""
    lines = [
        "请基于以下雷达页快照，给出今日 A 股洞察摘要：",
        "1. 市场主线与热点方向（参考板块·主线卡）",
        "2. 选股结果与发现/自选异动的交集（共振标的优先）",
        "3. 未来关注/可持/情景卡基于策略与统计情景（约 5 日），非价格预测",
        "4. 建议重点关注的 3～5 只标的及理由",
        "5. 不要编造未出现在数据中的价格或指标",
        "",
    ]
    resonance = compute_radar_resonance(payload)
    resonance_scores = compute_radar_resonance_scores(payload)
    if resonance:
        parts: list[str] = []
        for vt_symbol, count in sorted(
            resonance_scores.items(),
            key=lambda item: (-item[1], -resonance.get(item[0], 0), item[0]),
        ):
            item = parse_stock_symbol(vt_symbol)
            label = item.name if item and item.name else vt_symbol
            score = resonance_scores.get(vt_symbol, 0.0)
            parts.append(f"{label}({count}卡·{score:.1f}分)")
        lines.append(f"共振标的：{', '.join(parts)}")
        lines.append("")
    for data in payload.values():
        lines.append(f"## {data.title}")
        if data.subtitle:
            lines.append(data.subtitle)
        if data.updated_at:
            lines.append(f"更新：{data.updated_at}")
        if not data.rows:
            lines.append(data.empty_message or "（暂无数据）")
        else:
            for row in data.rows:
                marker = "★ " if row.vt_symbol in resonance else ""
                lines.append(f"- {marker}{_row_ai_summary(row)}")
        lines.append("")
    from vnpy_ashare.quotes.radar_horizon import build_outlook_ai_prompt

    for outlook_card_id in ("outlook_watch", "outlook_hold", "outlook_scenario"):
        outlook_prompt = build_outlook_ai_prompt(payload, card_id=outlook_card_id)
        if outlook_prompt:
            lines.append("---")
            lines.append(outlook_prompt)
    return "\n".join(lines).strip()
