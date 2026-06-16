"""雷达预测：从本地 K 线补全因子（推理用）。"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from vnpy_ashare.data.bar_access import load_scope_bars
from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.quotes.radar.predict.factor_panel import features_from_bar_window


def enrich_quote_rows_with_bar_features(rows: list[dict[str, Any]], *, max_compute: int = 120) -> list[dict[str, Any]]:
    """为行情行附加 predict_features（限量计算，避免全市场逐只读 K 线）。"""
    if not rows:
        return []
    capped = rows[: max(1, int(max_compute))]
    tail = rows[max(1, int(max_compute)) :]
    enriched: list[dict[str, Any]] = []
    for row in capped:
        merged = dict(row)
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        item = parse_stock_symbol(vt_symbol)
        if item is None:
            enriched.append(merged)
            continue
        bars = load_scope_bars(
            item.symbol,
            item.exchange,
            "daily",
            datetime(1990, 1, 1),
            datetime.now(),
        )
        if len(bars) < 25:
            enriched.append(merged)
            continue
        closes = [float(bar.close_price) for bar in bars]
        volumes = [float(bar.volume) for bar in bars]
        features = features_from_bar_window(
            closes,
            volumes,
            end_index=len(closes) - 1,
            turnover_rate=float(row.get("turnover_rate") or 0.0),
        )
        if features is not None:
            merged["predict_features"] = features
        enriched.append(merged)
    enriched.extend(dict(row) for row in tail)
    return enriched
