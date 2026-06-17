"""发现·连板梯队 loader。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from typing import Any, Literal

from vnpy_ashare.domain.market.quote_row import QuoteRowLike, quote_row_to_dict
from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.core.enrich import get_cached_limit_times_map
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, merge_row_quotes
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.hard_filters import apply_screening_filters, is_at_limit_board
from vnpy_ashare.screener.sector.sector_summary import attach_industry

LimitLadderVariant = Literal["by_height", "by_sector"]

_LADDER_BUCKET_ORDER = ("5板+", "4板", "3板", "2板", "首板")
LADDER_BUCKET_LABELS: tuple[str, ...] = _LADDER_BUCKET_ORDER


def ladder_bucket_label(boards: int) -> str:
    if boards >= 5:
        return "5板+"
    if boards == 4:
        return "4板"
    if boards == 3:
        return "3板"
    if boards == 2:
        return "2板"
    if boards == 1:
        return "首板"
    return ""


def board_display_text(boards: int) -> str:
    if boards >= 2:
        return f"{boards}板"
    if boards == 1:
        return "首板"
    return "—"


def _tickflow_key(row: QuoteRowLike) -> str:
    payload = quote_row_to_dict(row)
    vt_symbol = str(payload.get("vt_symbol") or "").strip()
    item = parse_stock_symbol(vt_symbol)
    if item is not None:
        return item.tickflow_symbol
    return vt_symbol.split(".")[0]


def resolve_limit_times(row: QuoteRowLike, *, limit_times_map: dict[str, float] | None = None) -> int:
    merged = merge_row_quotes(quote_row_to_dict(row))
    boards = int(float(merged.get("limit_times") or 0))
    if boards >= 1:
        return boards
    limit_map = limit_times_map if limit_times_map is not None else get_cached_limit_times_map()
    mapped = int(float(limit_map.get(_tickflow_key(merged)) or 0))
    if mapped >= 1:
        return mapped
    if is_at_limit_board(merged):
        return 1
    return 0


def enrich_limit_times(row: QuoteRowLike, *, limit_times_map: dict[str, float] | None = None) -> dict[str, Any]:
    merged = dict(merge_row_quotes(quote_row_to_dict(row)))
    boards = resolve_limit_times(merged, limit_times_map=limit_times_map)
    if boards >= 1:
        merged["limit_times"] = boards
    return merged


def build_limit_ladder_candidates(
    rows: Sequence[QuoteRowLike],
    *,
    limit_times_map: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """涨停池：limit_times ≥ 1 或近似涨停，经硬过滤。"""
    enriched = [enrich_limit_times(row, limit_times_map=limit_times_map) for row in rows]
    limit_up = [row for row in enriched if resolve_limit_times(row, limit_times_map=limit_times_map) >= 1]
    return [quote_row_to_dict(row) for row in apply_screening_filters(limit_up)]


def count_ladder_buckets(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {label: 0 for label in _LADDER_BUCKET_ORDER}
    for row in candidates:
        label = ladder_bucket_label(resolve_limit_times(row))
        if label:
            counts[label] = counts.get(label, 0) + 1
    return counts


def build_ladder_subtitle(*, counts: dict[str, int], total_scanned: int, variant_label: str) -> str:
    parts = [f"{label}×{counts[label]}" for label in _LADDER_BUCKET_ORDER if counts.get(label)]
    subtitle = variant_label
    if parts:
        subtitle += " · " + " · ".join(parts)
    if total_scanned:
        subtitle += f" · 扫描 {total_scanned} 只"
    return subtitle


def _sort_key(row: dict[str, Any]) -> tuple[int, float, float]:
    boards = resolve_limit_times(row)
    amount = float(row.get("amount") or 0)
    change = float(row.get("change_pct") or 0)
    return boards, amount, change


def select_by_height(candidates: list[dict[str, Any]], *, top_n: int) -> list[dict[str, Any]]:
    ranked = sorted(candidates, key=_sort_key, reverse=True)
    return ranked[:top_n]


def select_by_sector(candidates: list[dict[str, Any]], *, top_n: int) -> list[dict[str, Any]]:
    """每行业取连板最高的一只，再按高度与成交额排序。"""
    by_industry: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        industry = str(row.get("industry") or "").strip() or "—"
        by_industry[industry].append(row)

    picked: list[dict[str, Any]] = []
    for industry_rows in by_industry.values():
        best = max(industry_rows, key=_sort_key)
        picked.append(best)
    ranked = sorted(picked, key=_sort_key, reverse=True)
    return ranked[:top_n]


def _row_to_radar(row: dict[str, Any]) -> RadarRow | None:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return None
    item = parse_stock_symbol(vt_symbol)
    merged = merge_row_quotes(row)
    name = str(merged.get("name") or (item.name if item else "") or vt_symbol)
    symbol = str(merged.get("symbol") or (item.symbol if item else vt_symbol.split(".")[0]))
    price_raw = merged.get("last_price") or merged.get("close")
    price = float(price_raw) if isinstance(price_raw, (int, float)) else None
    change_raw = merged.get("change_pct")
    change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
    boards = resolve_limit_times(merged)
    industry = str(merged.get("industry") or "—")
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=symbol,
        price=price,
        change_pct=change_pct,
        metric_label="连板",
        metric_value=board_display_text(boards),
        sub_label="行业",
        sub_value=industry[:8],
        limit_times=float(boards) if boards >= 1 else None,
    )


def load_limit_ladder(spec: RadarCardSpec, *, variant: LimitLadderVariant = "by_height") -> RadarCardData:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="",
            rows=(),
            empty_message="暂无行情数据，请先采集行情或打开「市场」页。",
            updated_at="",
        )

    enriched = attach_industry(snapshot.rows)
    limit_map = get_cached_limit_times_map()
    candidates = build_limit_ladder_candidates(enriched, limit_times_map=limit_map)
    counts = count_ladder_buckets(candidates)
    variant_label = "按高度" if variant == "by_height" else "按板块"

    if not candidates:
        subtitle = build_ladder_subtitle(counts=counts, total_scanned=snapshot.total, variant_label=variant_label)
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=subtitle,
            rows=(),
            empty_message="暂无涨停梯队，请同步行情或等待盘中涨停数据。",
            updated_at="",
            total_count=snapshot.total,
        )

    if variant == "by_sector":
        selected = select_by_sector(candidates, top_n=spec.top_n)
    else:
        selected = select_by_height(candidates, top_n=spec.top_n)

    rows: list[RadarRow] = []
    for row in selected:
        parsed = _row_to_radar(row)
        if parsed is not None:
            rows.append(parsed)

    subtitle = build_ladder_subtitle(counts=counts, total_scanned=snapshot.total, variant_label=variant_label)
    if rows:
        subtitle += f" · 展示 {len(rows)}"

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=tuple(rows),
        empty_message="",
        updated_at="",
        total_count=len(candidates),
    )
