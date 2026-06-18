"""行业/板块汇总（选股解读与 sector_strength 维度共用）。"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, quote_row_copy, QuoteRowLike, QuoteRowsLike
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow, ScreeningFilterRow, screening_row_to_dict
from vnpy_ashare.domain.symbols.stock import vt_symbol_to_ts_code
from vnpy_ashare.integrations.tushare.concept_board import build_hot_concept_vt_symbol_map
from vnpy_ashare.integrations.tushare.factors import fetch_stock_industry_map


def attach_industry(
    rows: Sequence[ScreeningFilterRow | Mapping[str, Any]],
    industry_map: dict[str, str] | None = None,
) -> list[QuoteRow]:
    """为行情行附加 ``industry`` 字段。"""
    mapping = industry_map if industry_map is not None else fetch_stock_industry_map()
    enriched: list[QuoteRow] = []
    for row in rows:
        payload = screening_row_to_dict(row)
        ts_code = vt_symbol_to_ts_code(str(payload.get("vt_symbol") or ""))
        industry = mapping.get(ts_code or "", "").strip() if ts_code else ""
        if not industry:
            continue
        quote = row.quote if isinstance(row, ScreenerResultRow) else row
        enriched.append(quote_row_copy(quote, industry=industry))
    return enriched


def attach_concept(
    rows: QuoteRowsLike,
    vt_to_concept: dict[str, str] | None = None,
) -> list[QuoteRow]:
    """为行情行附加 ``concept`` 字段（主概念名）。"""
    if vt_to_concept is None:
        mapping, _hot = build_hot_concept_vt_symbol_map()
    else:
        mapping = vt_to_concept

    enriched: list[QuoteRow] = []
    for row in rows:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        concept = mapping.get(vt_symbol, "").strip()
        if not concept:
            continue
        enriched.append(quote_row_copy(row, concept=concept))
    return enriched


def attach_sector_fields(
    rows: QuoteRowsLike,
    *,
    industry_map: dict[str, str] | None = None,
    vt_to_concept: dict[str, str] | None = None,
) -> tuple[list[QuoteRow], list[str]]:
    """附加行业 + 概念；至少有一轴则保留。返回 (rows, hot_concept_names)。"""
    mapping = industry_map if industry_map is not None else fetch_stock_industry_map()
    if vt_to_concept is None:
        concept_map, hot_names = build_hot_concept_vt_symbol_map()
    else:
        concept_map = vt_to_concept
        hot_names = sorted({name for name in concept_map.values() if name})

    enriched: list[QuoteRow] = []
    for row in rows:
        ts_code = vt_symbol_to_ts_code(str(row.get("vt_symbol") or ""))
        industry = mapping.get(ts_code or "", "").strip() if ts_code else ""
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        concept = concept_map.get(vt_symbol, "").strip()
        if not industry and not concept:
            continue
        updates: dict[str, Any] = {}
        if industry:
            updates["industry"] = industry
        if concept:
            updates["concept"] = concept
        enriched.append(quote_row_copy(row, **updates))
    return enriched, hot_names


def compute_sector_distribution(
    rows: QuoteRowsLike,
    *,
    top_n: int = 8,
    min_stocks: int = 2,
    sector_field: str = "industry",
) -> list[dict[str, Any]]:
    """按行业/概念统计标的数、上涨占比与平均涨幅，降序返回 Top N。"""
    buckets: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        sector = str(row.get(sector_field) or "").strip()
        if not sector:
            continue
        pct = float(row.get("change_pct") or row.get("pct_chg") or 0)
        buckets[sector].append(pct)

    stats: list[dict[str, Any]] = []
    for sector, pcts in buckets.items():
        if len(pcts) < min_stocks:
            continue
        avg_pct = sum(pcts) / len(pcts)
        positive = sum(1 for pct in pcts if pct > 0)
        advance_ratio = positive / len(pcts)
        stats.append(
            {
                "industry": sector,
                sector_field: sector,
                "count": len(pcts),
                "avg_change_pct": round(avg_pct, 2),
                "advance_ratio": round(advance_ratio, 4),
                "advance_pct": round(advance_ratio * 100, 1),
            }
        )
    stats.sort(
        key=lambda item: (
            float(item["avg_change_pct"]),
            float(item["advance_ratio"]),
            int(item["count"]),
        ),
        reverse=True,
    )
    return stats[: max(1, top_n)]


def top_industries_by_momentum(
    rows: QuoteRowsLike,
    *,
    top_industry_count: int = 5,
    min_stocks_per_industry: int = 3,
) -> list[str]:
    """返回当日平均涨幅靠前的行业名列表。"""
    distribution = compute_sector_distribution(
        rows,
        top_n=top_industry_count * 2,
        min_stocks=min_stocks_per_industry,
    )
    return [str(item["industry"]) for item in distribution[:top_industry_count]]


def top_industries_by_breadth(
    rows: QuoteRowsLike,
    *,
    top_industry_count: int = 5,
    min_stocks_per_industry: int = 3,
) -> list[dict[str, Any]]:
    """按上涨家数占比排序的行业统计（广度扩散）。"""
    distribution = compute_sector_distribution(
        rows,
        top_n=top_industry_count * 3,
        min_stocks=min_stocks_per_industry,
    )
    ranked = sorted(
        distribution,
        key=lambda item: (
            float(item.get("advance_ratio") or 0),
            float(item.get("avg_change_pct") or 0),
            int(item.get("count") or 0),
        ),
        reverse=True,
    )
    return ranked[:top_industry_count]


def breadth_leader_candidates(
    rows: QuoteRowsLike,
    *,
    pool_size: int,
    min_stocks_per_industry: int = 3,
) -> list[QuoteRow]:
    """广度扩散：强势行业内按个股涨幅取候选。"""
    strong = top_industries_by_breadth(
        rows,
        top_industry_count=5,
        min_stocks_per_industry=min_stocks_per_industry,
    )
    if not strong:
        return []

    industry_names = {str(item["industry"]) for item in strong}
    buckets: dict[str, list[QuoteRow]] = defaultdict(list)
    for row in rows:
        industry = str(row.get("industry") or "").strip()
        if industry in industry_names:
            buckets[industry].append(quote_row_copy(row))

    candidates: list[QuoteRow] = []
    stat_map = {str(item["industry"]): item for item in strong}
    for industry, items in buckets.items():
        stat = stat_map.get(industry, {})
        ranked = sorted(items, key=lambda item: float(item.get("change_pct") or 0), reverse=True)
        for item in ranked[: max(2, pool_size // 5)]:
            candidates.append(
                quote_row_copy(
                    item,
                    breadth_ratio=float(stat.get("advance_pct") or 0),
                    industry_avg_change=float(stat.get("avg_change_pct") or 0),
                )
            )

    candidates.sort(
        key=lambda item: (
            float(item.get("breadth_ratio") or 0),
            float(item.get("change_pct") or 0),
        ),
        reverse=True,
    )
    return candidates[:pool_size]
