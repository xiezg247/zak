"""自选·短线关注 loader。"""

from __future__ import annotations

from vnpy_ashare.config.constants.watchlist import SHORT_TERM_FOCUS_GROUP_NAME
from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_models import RadarCardData
from vnpy_ashare.quotes.radar.radar_pool import collect_short_term_focus_vt_symbols, name_map_for_symbols
from vnpy_ashare.quotes.radar.radar_watchlist import (
    _has_quote_data,
    _quotes_for_candidates,
    _row_from_quote,
    _score_candidates,
    enrich_quotes_with_moneyflow,
    load_watchlist_signal_config,
)


def load_watchlist_short_term(spec: RadarCardSpec) -> RadarCardData:
    candidates = collect_short_term_focus_vt_symbols(max_items=spec.top_n * 3)
    if not candidates:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="",
            rows=(),
            empty_message=f"「{SHORT_TERM_FOCUS_GROUP_NAME}」分组暂无标的。可在共振侧栏写入或手动添加。",
            updated_at=format_china_datetime_minute(),
        )

    _ = load_watchlist_signal_config()
    quotes_by_vt = enrich_quotes_with_moneyflow(_quotes_for_candidates(candidates))
    name_map = name_map_for_symbols(candidates)
    has_any_quote = any(_has_quote_data(row) for row in quotes_by_vt.values())

    scored = _score_candidates(candidates, quotes_by_vt, {}, anomaly_only=False)
    top_scored = scored[: spec.top_n]

    rows = []
    for vt_symbol, row, _score, _transition in top_scored:
        parsed = _row_from_quote(vt_symbol, row, name_map=name_map)
        if parsed is not None:
            rows.append(parsed)

    subtitle = f"{SHORT_TERM_FOCUS_GROUP_NAME} {len(candidates)} 只"
    if not has_any_quote:
        subtitle += " · 行情待采集"
    else:
        subtitle += f" · 展示 Top {len(rows)}"

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=tuple(rows),
        empty_message="",
        updated_at=format_china_datetime_minute(),
        total_count=len(candidates),
    )
