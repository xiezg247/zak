"""形态选股执行（扫描本地日 K）。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from vnpy.trader.constant import Exchange
from vnpy.trader.object import BarData

from vnpy_ashare.bars import load_downloaded_stocks
from vnpy_ashare.models import StockItem
from vnpy_ashare.screener.export import resolve_export_columns
from vnpy_ashare.screener.pattern_rules import PATTERN_MATCHERS, BarSeries, PatternMatch
from vnpy_ashare.screener.presets import SCREENER_CUSTOM
from vnpy_ashare.screener.rules import apply_quote_preset
from vnpy_ashare.screener.runner import ScreenerRunResult

MAX_PATTERN_SCAN = 1200

_PATTERN_ALIASES: dict[str, str] = {
    "老鸭头": "old_duck",
    "老鸭头形态": "old_duck",
    "均线多头": "ma_bull",
    "均线多头排列": "ma_bull",
    "w底": "w_bottom",
    "w底形态": "w_bottom",
    "双底": "w_bottom",
    "主题投资": "theme_hot",
    "热点主题": "theme_hot",
}

_PATTERN_LABELS: dict[str, str] = {
    "ma_bull": "均线多头",
    "old_duck": "老鸭头形态",
    "w_bottom": "W底形态",
    "theme_hot": "主题投资",
}


@dataclass(frozen=True)
class PatternScreenInput:
    pattern: str
    top_n: int = 20


def normalize_pattern_id(name: str) -> str:
    key = (name or "").strip()
    if not key:
        return ""
    lowered = key.lower().replace(" ", "")
    for alias, pattern_id in _PATTERN_ALIASES.items():
        if alias.lower().replace(" ", "") == lowered:
            return pattern_id
    if key in _PATTERN_LABELS:
        return key
    return ""


def pattern_label(pattern_id: str) -> str:
    return _PATTERN_LABELS.get(pattern_id, pattern_id)


def list_pattern_screeners() -> list[str]:
    return [pattern_label(pid) for pid in _PATTERN_LABELS]


def _row_from_match(
    item: StockItem,
    match: PatternMatch,
    *,
    last_close: float,
    change_pct: float | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "symbol": item.symbol,
        "name": item.name,
        "vt_symbol": item.vt_symbol,
        "exchange": item.exchange.value,
        "last_price": round(last_close, 2),
        "pattern_score": match.score,
        "pattern_hint": match.hint,
    }
    if change_pct is not None:
        row["change_pct"] = round(change_pct, 2)
    return row


def _calc_change_pct(closes: list[float]) -> float | None:
    if len(closes) < 2 or closes[-2] <= 0:
        return None
    return (closes[-1] - closes[-2]) / closes[-2] * 100


def run_pattern_screen(
    pattern_id: str,
    *,
    top_n: int = 20,
    load_bars: Callable[[str, Exchange], list[BarData]],
    quote_rows: list[dict[str, Any]] | None = None,
    max_scan: int = MAX_PATTERN_SCAN,
) -> ScreenerRunResult:
    """扫描本地日 K（或行情快照）执行形态选股。"""
    top_n = max(1, min(int(top_n or 20), 200))
    label = pattern_label(pattern_id)

    if pattern_id == "theme_hot":
        if not quote_rows:
            raise RuntimeError("主题投资需全市场行情。请运行「工具 → 立即执行 → 行情采集」或打开市场页。")
        rows = apply_quote_preset(
            SCREENER_CUSTOM,
            quote_rows,
            top_n=top_n,
            min_change_pct=2.0,
            min_turnover=3.0,
        )
        for row in rows:
            row["pattern_score"] = round(
                float(row.get("turnover_rate") or 0) * max(float(row.get("change_pct") or 0), 0.1),
                2,
            )
            row["pattern_hint"] = "高换手 + 涨幅活跃"
        rows.sort(key=lambda item: float(item.get("pattern_score") or 0), reverse=True)
        return ScreenerRunResult(
            rows=rows[:top_n],
            condition=f"形态 · {label}",
            updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_scanned=len(quote_rows),
            source="quote",
            columns=resolve_export_columns(rows),
        )

    matcher = PATTERN_MATCHERS.get(pattern_id)
    if matcher is None:
        raise ValueError(f"未知形态：{pattern_id}")

    stocks = load_downloaded_stocks(scope="daily")
    if not stocks:
        raise RuntimeError("本地暂无日 K 数据。请先在自选/本地页下载日 K 后再做形态选股。")

    scanned = 0
    hits: list[tuple[float, dict[str, Any]]] = []
    for item in stocks[:max_scan]:
        bars = load_bars(item.symbol, item.exchange)
        if len(bars) < 60:
            continue
        scanned += 1
        series = BarSeries.from_bars(bars)
        match = matcher(series)
        if match is None:
            continue
        change_pct = _calc_change_pct(series.closes)
        row = _row_from_match(item, match, last_close=series.closes[-1], change_pct=change_pct)
        hits.append((match.score, row))

    hits.sort(key=lambda pair: pair[0], reverse=True)
    rows = [row for _, row in hits[:top_n]]
    return ScreenerRunResult(
        rows=rows,
        condition=f"形态 · {label}",
        updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        total_scanned=scanned,
        source="bar",
        columns=resolve_export_columns(rows),
    )


def resolve_pattern_screen(data: PatternScreenInput) -> tuple[str, str]:
    """返回 (pattern_id, error)。"""
    pattern_id = normalize_pattern_id(data.pattern)
    if not pattern_id:
        return "", f"未知形态「{data.pattern}」，可用：{', '.join(list_pattern_screeners())}"
    return pattern_id, ""
