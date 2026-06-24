"""形态选股：优先通达信问小达 MCP，失败时由 pattern_screen 本地降级。"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.screener.result_row import coerce_screener_result_rows
from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.screener.hard_filters import apply_recipe_filters
from vnpy_ashare.screener.pattern.pattern_screen import pattern_label
from vnpy_ashare.screener.run.result import ScreenerRunResult, build_screener_run_result

_McpExecute = Callable[[str, dict[str, Any]], str]
_WENDA_TOOL_KEYWORDS = ("wenda", "问小达")

_PATTERN_QUESTIONS: dict[str, str] = {
    "old_duck": "A股市场中符合老鸭头形态的股票有哪些",
    "ma_bull": "A股市场中均线多头排列的股票有哪些",
    "w_bottom": "A股市场中W底形态的股票有哪些",
    "theme_hot": "A股市场中高换手涨幅活跃的热点股票有哪些",
}

_HEADER_TAG_RE = re.compile(r"<[^>]+>")


def _pick_wenda_tool(tool_names: list[str]) -> str | None:
    for name in tool_names:
        lower = name.lower()
        if lower.startswith("mcp_tdx_"):
            lower = lower.removeprefix("mcp_tdx_")
        if any(keyword in lower for keyword in _WENDA_TOOL_KEYWORDS):
            return name
    return None


def _clean_header(text: str) -> str:
    return _HEADER_TAG_RE.sub("", text).strip()


def _market_to_exchange(market: str) -> Exchange:
    if str(market).strip() == "1":
        return Exchange.SSE
    return Exchange.SZSE


def _field_index(headers: list[Any], *candidates: str) -> int | None:
    normalized = [_clean_header(str(item)).lower() for item in headers]
    for candidate in candidates:
        key = candidate.lower()
        for index, header in enumerate(normalized):
            if key in header or header in key:
                return index
    return None


def parse_wenda_screen_rows(raw_text: str, *, top_n: int = 20) -> tuple[list[dict[str, Any]], int]:
    """解析问小达多行选股结果 → screener rows。"""
    text = (raw_text or "").strip()
    if not text:
        return [], 0
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [], 0
    if not isinstance(payload, dict):
        return [], 0

    headers = payload.get("headers") or []
    data = payload.get("data") or []
    if not isinstance(headers, list) or not isinstance(data, list):
        return [], 0

    code_idx = _field_index(headers, "sec_code", "代码", "symbol")
    name_idx = _field_index(headers, "sec_name", "名称", "name")
    price_idx = _field_index(headers, "now_price", "现价", "price", "last_price")
    change_idx = _field_index(headers, "chg0#", "涨跌幅", "change_pct", "涨幅")
    hint_idx = len(headers) - 1 if headers else None

    rows: list[dict[str, Any]] = []
    for raw_row in data[: max(1, min(int(top_n or 20), 200))]:
        if not isinstance(raw_row, list):
            continue
        if code_idx is None or code_idx >= len(raw_row):
            continue
        symbol = str(raw_row[code_idx]).strip()
        if not symbol or not symbol.isdigit():
            continue
        market = str(raw_row[1]).strip() if len(raw_row) > 1 else "0"
        exchange = _market_to_exchange(market)
        name = str(raw_row[name_idx]).strip() if name_idx is not None and name_idx < len(raw_row) else ""
        row: dict[str, Any] = {
            "symbol": symbol,
            "name": name,
            "vt_symbol": f"{symbol}.{exchange.value}",
            "exchange": exchange.value,
            "pattern_hint": "通达信问小达",
        }
        if price_idx is not None and price_idx < len(raw_row):
            try:
                row["last_price"] = round(float(raw_row[price_idx]), 2)
            except (TypeError, ValueError):
                pass
        if change_idx is not None and change_idx < len(raw_row):
            try:
                row["change_pct"] = round(float(raw_row[change_idx]), 2)
            except (TypeError, ValueError):
                pass
        if hint_idx is not None and hint_idx < len(raw_row):
            hint = str(raw_row[hint_idx]).strip()
            if hint:
                row["pattern_hint"] = hint
        if len(raw_row) > 7:
            detail = str(raw_row[7]).strip()
            if detail:
                row["pattern_detail"] = detail
        pos = len(rows) + 1
        row["pattern_score"] = max(100 - pos, 1)
        rows.append(row)

    total = 0
    meta = payload.get("meta")
    if isinstance(meta, dict):
        try:
            total = int(meta.get("total") or len(data))
        except (TypeError, ValueError):
            total = len(data)
    else:
        total = len(data)
    return rows, total


def run_pattern_screen_mcp(
    pattern_id: str,
    *,
    mcp_execute: _McpExecute | None,
    tool_names: list[str] | None,
    top_n: int = 20,
) -> ScreenerRunResult | None:
    """问小达 MCP 形态选股；不可用时返回 None 供本地降级。"""
    if mcp_execute is None or not tool_names:
        return None
    tool_name = _pick_wenda_tool(tool_names)
    question = _PATTERN_QUESTIONS.get(pattern_id)
    if tool_name is None or not question:
        return None

    top_n = max(1, min(int(top_n or 20), 200))
    try:
        raw = mcp_execute(tool_name, {"question": question, "range": "AG"})
    except Exception:
        return None

    # 多取候选，硬过滤 ST / 停牌 / 流动性后再截断 top_n
    rows, total_scanned = parse_wenda_screen_rows(raw, top_n=max(top_n * 5, top_n + 12))
    filtered_rows = apply_recipe_filters(rows)[:top_n]
    if not filtered_rows:
        return None

    label = pattern_label(pattern_id)
    return build_screener_run_result(
        rows=coerce_screener_result_rows(filtered_rows),
        condition=f"形态 · {label}",
        updated_at=format_china_datetime(),
        total_scanned=total_scanned,
        source="mcp",
    )
