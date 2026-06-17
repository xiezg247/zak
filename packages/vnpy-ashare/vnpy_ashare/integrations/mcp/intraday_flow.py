"""盘中主力资金：可选绑定 TDX MCP 执行器（定时任务无 Engine 时自动降级）。"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable, Sequence
from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRowLike
from vnpy_ashare.domain.symbols import vt_symbol_to_symbol

_McpExecutor = Callable[[str, dict[str, Any]], str]
_mcp_execute: _McpExecutor | None = None
_mcp_tool_names: list[str] | None = None

_FLOW_TOOL_KEYWORDS = ("moneyflow", "zijin", "资金", "main_net", "净流入")
_WENDA_TOOL_KEYWORDS = ("wenda", "问小达")


def bind_mcp_intraday_flow(
    *,
    execute: _McpExecutor | None,
    tool_names: list[str] | None = None,
) -> None:
    """由 ScreeningService / LlmEngine 注入 MCP 能力。"""
    global _mcp_execute, _mcp_tool_names
    _mcp_execute = execute
    _mcp_tool_names = list(tool_names or [])


def mcp_intraday_flow_enabled() -> bool:
    if os.getenv("MCP_INTRADAY_FLOW", "0").strip().lower() in ("0", "false", "no"):
        return False
    return _mcp_execute is not None and bool(_mcp_tool_names)


def fetch_intraday_moneyflow_map(
    rows: Sequence[QuoteRowLike],
    *,
    top_n: int = 40,
) -> dict[str, float]:
    """对候选标的批量查询主力净流入（万）；失败返回空 dict。"""
    if not mcp_intraday_flow_enabled() or not rows:
        return {}

    tool = _pick_flow_tool()
    if tool is None:
        return {}

    symbols = [str(row.get("vt_symbol") or "") for row in rows if row.get("vt_symbol")]
    symbols = symbols[: max(1, min(top_n, 60))]
    result: dict[str, float] = {}
    for vt_symbol in symbols:
        symbol = vt_symbol_to_symbol(vt_symbol)
        amount = _query_symbol_flow(tool, vt_symbol, symbol)
        if amount is not None:
            result[vt_symbol] = amount
    return result


def _pick_flow_tool() -> str | None:
    names = _mcp_tool_names or []
    for name in names:
        lower = name.lower()
        if lower.startswith("mcp_tdx_"):
            lower = lower.removeprefix("mcp_tdx_")
        if any(keyword in lower for keyword in _FLOW_TOOL_KEYWORDS):
            return name
    for name in names:
        lower = name.lower()
        if any(keyword in lower for keyword in _WENDA_TOOL_KEYWORDS):
            return name
    return None


def _query_symbol_flow(tool_name: str, vt_symbol: str, symbol: str) -> float | None:
    if _mcp_execute is None:
        return None
    args = {"code": symbol, "symbol": symbol, "stock_code": symbol, "vt_symbol": vt_symbol}
    try:
        raw = _mcp_execute(tool_name, args)
    except Exception:
        return None
    return _parse_flow_amount(raw)


def _parse_flow_amount(raw: str) -> float | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return _parse_flow_from_text(text)

    if isinstance(payload, (int, float)):
        return float(payload)
    if isinstance(payload, list):
        for item in payload:
            value = _extract_amount_field(item)
            if value is not None:
                return value
        return None
    if isinstance(payload, dict):
        for key in ("net_mf_amount", "main_net_inflow", "net_inflow", "amount", "value"):
            if key in payload:
                try:
                    return float(payload[key])
                except (TypeError, ValueError):
                    continue
        for nested in ("data", "result", "items"):
            value = payload.get(nested)
            if isinstance(value, list) and value:
                amount = _extract_amount_field(value[0])
                if amount is not None:
                    return amount
        text_field = str(payload.get("text") or "")
        if text_field:
            return _parse_flow_from_text(text_field)
    return None


def _extract_amount_field(item: Any) -> float | None:
    if not isinstance(item, dict):
        return None
    for key in ("net_mf_amount", "main_net_inflow", "net_inflow", "amount"):
        if key in item:
            try:
                return float(item[key])
            except (TypeError, ValueError):
                continue
    return None


def _parse_flow_from_text(text: str) -> float | None:

    patterns = (
        r"主力净流入[^\d\-+]*([\-+]?\d+(?:\.\d+)?)",
        r"净流入[^\d\-+]*([\-+]?\d+(?:\.\d+)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                continue
    return None
