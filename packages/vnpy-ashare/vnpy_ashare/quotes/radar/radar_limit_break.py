"""发现·炸板断板 loader。"""

from __future__ import annotations

from vnpy_ashare.domain.symbols.stock import parse_stock_symbol, ts_code_to_vt_symbol
from vnpy_ashare.integrations.tushare.factors import fetch_limit_list_d
from vnpy_ashare.quotes.format import format_pct
from vnpy_ashare.quotes.radar.radar_catalog import RadarCardSpec
from vnpy_ashare.quotes.radar.radar_limit_ladder import board_display_text, resolve_limit_times
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, RadarRow, merge_row_quotes
from vnpy_ashare.quotes.radar.radar_pool import name_map_for_symbols
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.hard_filters import apply_screening_filters, is_at_limit_board, limit_board_threshold_pct
from vnpy_ashare.trading.signals.seal_reopen import classify_seal_reopen, format_seal_reopen_label

_BREAK_KINDS = frozenset({"broken", "weak"})


def _is_limit_down(row: dict) -> bool:
    change = float(row.get("change_pct") or row.get("pct_chg") or 0)
    threshold = limit_board_threshold_pct(row)
    return change <= -threshold


def _severity_key(kind: str, *, boards: int, change: float) -> tuple[int, float]:
    if kind == "limit_down":
        return 0, abs(change)
    if kind == "broken_board":
        return 1, boards
    if kind == "seal_break":
        return 2, abs(change)
    return 9, 0.0


def _collect_limit_break_candidates(snapshot_rows: list) -> list[tuple[dict, str, str, str]]:
    """返回 (row, kind, metric_label, metric_value)。"""
    by_vt: dict[str, dict] = {}
    for row in apply_screening_filters(snapshot_rows):
        vt = str(row.get("vt_symbol") or "").strip()
        if vt:
            by_vt[vt] = merge_row_quotes(row)

    results: list[tuple[dict, str, str, str]] = []
    seen: set[str] = set()

    limit_rows, _ = fetch_limit_list_d()
    open_times_by_vt: dict[str, int | None] = {}
    for item in limit_rows:
        ts_code = str(item.get("ts_code") or "").strip()
        vt = str(item.get("vt_symbol") or "").strip()
        if not vt and ts_code:
            vt = ts_code_to_vt_symbol(ts_code)
        if not vt:
            continue
        raw = item.get("open_times")
        try:
            open_times_by_vt[vt] = int(float(raw)) if raw not in (None, "") else None
        except (TypeError, ValueError):
            open_times_by_vt[vt] = None

    for vt, row in by_vt.items():
        if _is_limit_down(row):
            results.append((row, "limit_down", "跌停", format_pct(float(row.get("change_pct") or 0))))
            seen.add(vt)

    for vt, row in by_vt.items():
        if vt in seen:
            continue
        boards = resolve_limit_times(row)
        change = float(row.get("change_pct") or 0)
        if boards >= 2 and change <= -3.0 and not is_at_limit_board(row):
            results.append((row, "broken_board", "断板", board_display_text(boards)))
            seen.add(vt)

    for vt, row in by_vt.items():
        if vt in seen:
            continue
        if not is_at_limit_board(row):
            continue
        open_times = open_times_by_vt.get(vt)
        kind = classify_seal_reopen(open_times=open_times, at_limit=True)
        if kind in _BREAK_KINDS:
            label = format_seal_reopen_label(kind, open_times=open_times) or "炸板"
            results.append((row, "seal_break", "封板", label[:12]))
            seen.add(vt)

    results.sort(
        key=lambda item: _severity_key(
            item[1],
            boards=resolve_limit_times(item[0]),
            change=float(item[0].get("change_pct") or 0),
        ),
    )
    return results


def load_discovery_limit_break(spec: RadarCardSpec) -> RadarCardData:
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="",
            rows=(),
            empty_message="暂无行情数据，请先采集行情。",
            updated_at="",
        )

    candidates = _collect_limit_break_candidates(list(snapshot.rows))
    if not candidates:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle=f"扫描 {snapshot.total} 只",
            rows=(),
            empty_message="当前无明显跌停 / 断板 / 炸板风险标的。",
            updated_at="",
            total_count=int(snapshot.total or 0),
        )

    vt_symbols = [str(item[0].get("vt_symbol") or "") for item in candidates[: spec.top_n]]
    name_map = name_map_for_symbols([vt for vt in vt_symbols if vt])
    rows: list[RadarRow] = []
    limit_down = broken = seal = 0
    for row, kind, metric_label, metric_value in candidates[: spec.top_n]:
        vt_symbol = str(row.get("vt_symbol") or "").strip()
        if not vt_symbol:
            continue
        if kind == "limit_down":
            limit_down += 1
        elif kind == "broken_board":
            broken += 1
        else:
            seal += 1
        item = parse_stock_symbol(vt_symbol)
        name = name_map.get(vt_symbol) or str(row.get("name") or (item.name if item else "") or vt_symbol)
        symbol = str(row.get("symbol") or (item.symbol if item else vt_symbol.split(".")[0]))
        price_raw = row.get("last_price") or row.get("close")
        price = float(price_raw) if isinstance(price_raw, (int, float)) else None
        change_raw = row.get("change_pct")
        change_pct = float(change_raw) if isinstance(change_raw, (int, float)) else None
        boards = resolve_limit_times(row)
        rows.append(
            RadarRow(
                vt_symbol=vt_symbol,
                name=name,
                symbol=symbol,
                price=price,
                change_pct=change_pct,
                metric_label=metric_label,
                metric_value=metric_value,
                sub_label="连板" if boards >= 1 else "涨幅",
                sub_value=board_display_text(boards) if boards >= 1 else format_pct(change_pct),
                limit_times=boards if boards >= 1 else None,
            )
        )

    parts: list[str] = []
    if limit_down:
        parts.append(f"跌停 {limit_down}")
    if broken:
        parts.append(f"断板 {broken}")
    if seal:
        parts.append(f"炸板 {seal}")
    subtitle = " · ".join(parts) if parts else "风险异动"
    subtitle += f" · 扫描 {snapshot.total} 只"

    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=subtitle,
        rows=tuple(rows),
        empty_message="",
        updated_at="",
        total_count=len(rows),
    )
