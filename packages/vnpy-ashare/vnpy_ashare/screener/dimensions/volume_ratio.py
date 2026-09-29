"""量比维度：Tushare volume_ratio 与 Redis 行情合并。"""

from __future__ import annotations

from vnpy_ashare.integrations.tushare.factors import fetch_daily_basic
from vnpy_ashare.screener.dimensions.base import DimensionHit, dimension_hit_row, load_quote_snapshot_for_dimension
from vnpy_ashare.screener.dimensions.scoring import blended_score
from vnpy_ashare.screener.hard_filters import apply_recipe_filters


def run_volume_ratio(pool_size: int, *, weight: float) -> tuple[list[DimensionHit], int]:
    from vnpy_ashare.screener.engine.dimensions.volume_ratio import (
        run_volume_ratio_polars,
        volume_ratio_reason,
        volume_ratio_tier_factor,
    )

    loaded = load_quote_snapshot_for_dimension()
    if loaded is None:
        return _volume_ratio_from_tushare_only(
            pool_size,
            weight=weight,
            reason=volume_ratio_reason,
            tier_factor=volume_ratio_tier_factor,
        )

    rows, total = loaded
    result = run_volume_ratio_polars(
        rows,
        pool_size=pool_size,
        weight=weight,
        total=total,
    )
    if result is not None:
        return result
    return _volume_ratio_from_tushare_only(
        pool_size,
        weight=weight,
        reason=volume_ratio_reason,
        tier_factor=volume_ratio_tier_factor,
    )


def _volume_ratio_from_tushare_only(
    pool_size: int,
    *,
    weight: float,
    reason,
    tier_factor,
) -> tuple[list[DimensionHit], int]:
    try:
        basic_rows, _ = fetch_daily_basic()
    except Exception:
        return [], 0
    if not basic_rows:
        return [], 0
    filtered_rows = apply_recipe_filters(
        [row for row in basic_rows if float(row.get("volume_ratio") or 0) > 0],
    )
    sorted_rows = sorted(
        filtered_rows,
        key=lambda item: float(item.get("volume_ratio") or 0),
        reverse=True,
    )[:pool_size]
    hits: list[DimensionHit] = []
    for index, row in enumerate(sorted_rows, start=1):
        vt_symbol = str(row.get("vt_symbol") or "")
        if not vt_symbol:
            continue
        ratio = float(row.get("volume_ratio") or 0)
        base = blended_score(index, len(sorted_rows), ratio, [float(r.get("volume_ratio") or 0) for r in sorted_rows])
        hits.append(
            DimensionHit(
                vt_symbol=vt_symbol,
                dimension_id="volume_ratio",
                label="量比",
                weight=weight,
                score=round(base * tier_factor(ratio), 1),
                reason=reason({"volume_ratio": ratio}, index),
                row=dimension_hit_row(
                    {
                        "symbol": row.get("symbol", ""),
                        "name": row.get("name", ""),
                        "vt_symbol": vt_symbol,
                        "close": row.get("close", 0),
                        "volume_ratio": ratio,
                        "turnover_rate": row.get("turnover_rate", 0),
                        "source": "tushare",
                    }
                ),
            )
        )
    return hits, len(basic_rows)
