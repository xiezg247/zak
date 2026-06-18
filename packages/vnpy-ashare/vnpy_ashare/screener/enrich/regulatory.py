"""选股结果监管异动标签批量 enrichment。"""

from __future__ import annotations

from vnpy_ashare.data.pattern_bars import load_daily_bars_batch
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow, update_screening_row
from vnpy_ashare.domain.symbols.stock import StockItem, parse_stock_symbol
from vnpy_ashare.services.stock.regulatory_deviation import assess_regulatory_deviation


def enrich_regulatory_tags(rows: list[ScreenerResultRow]) -> list[ScreenerResultRow]:
    """为选股结果附加 regulatory_hint / regulatory_risk（需本地日 K）。"""
    if not rows:
        return rows

    items: list[StockItem] = []
    for row in rows:
        vt = str(row.get("vt_symbol") or "").strip()
        if not vt:
            continue
        item = parse_stock_symbol(vt)
        if item is not None:
            items.append(item)

    if not items:
        return rows

    bars_map = load_daily_bars_batch(items, lookback_bars=45)
    enriched: list[ScreenerResultRow] = []
    for row in rows:
        vt = str(row.get("vt_symbol") or "").strip()
        item = parse_stock_symbol(vt) if vt else None
        if item is None:
            enriched.append(row)
            continue
        bars = bars_map.get((item.symbol, item.exchange), [])
        if len(bars) < 11:
            enriched.append(row)
            continue
        snapshot = assess_regulatory_deviation(bars)
        if snapshot.risk_level == "none":
            enriched.append(row)
            continue
        enriched.append(
            update_screening_row(
                row,
                regulatory_hint=snapshot.summary,
                regulatory_risk=snapshot.risk_level,
            )
        )
    return enriched
