"""近期走势：本地 K 线 enriched + 问小达 MCP 兜底。"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.services.analysis.mcp_binding import McpBinding
from vnpy_ashare.services.analysis.tdx_diagnose import _call_wenda, _pick_wenda_tool, _to_float
from vnpy_ashare.services.analysis.technical import TechnicalAnalyzer

_DISCLAIMER = "以上均为历史区间统计或问小达返回的历史参考数据，不代表对未来走势的判断或预测。"
_MCP_SKIP_FIELDS = frozenset(
    {"POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业", "show_url"},
)
_RETURN_KEY_RE = re.compile(r"(\d+)\s*日")
_NEAR_LOOKBACK_RE = re.compile(r"近\s*(\d+)")


def local_historical_sufficient(result: dict[str, Any]) -> bool:
    """是否已有可用于解读的历史走势数据（本地统计或 MCP 兜底）。"""
    if result.get("error"):
        return False
    if result.get("return_pct") is not None:
        return True
    if result.get("data_quality") == "mcp_fallback" and result.get("mcp_fields"):
        return True
    return False


def fetch_historical_pattern_mcp(
    symbol: str,
    *,
    lookback: int,
    mcp: McpBinding,
) -> dict[str, Any]:
    """本地 K 不足时，经问小达 MCP 获取历史走势参考。"""
    item = parse_stock_symbol(symbol)
    if item is None:
        return {"error": f"无法解析代码: {symbol}"}

    lookback = max(5, min(int(lookback or 20), 120))
    base: dict[str, Any] = {
        "symbol": item.vt_symbol,
        "name": item.name,
        "scope": "daily",
        "lookback_days": lookback,
        "local_available": False,
        "sources": [],
        "disclaimer": _DISCLAIMER,
    }

    if mcp.execute is None or not mcp.tool_names:
        base["warnings"] = ["本地 K 线不足，且通达信 MCP 未连接（请配置 mcp/mcp.json）"]
        return base

    tool_name = _pick_wenda_tool(mcp.tool_names)
    if tool_name is None:
        base["warnings"] = ["本地 K 线不足，且未找到问小达 MCP 工具"]
        return base

    label = item.name or item.symbol
    warnings: list[str] = []
    merged_fields: dict[str, str] = {}

    queries = (
        (f"{label}{item.symbol}近{lookback}日涨跌幅走势波动", "trend"),
        (f"{label}{item.symbol}最新行情涨跌幅成交量", "quote"),
        (f"{label}{item.symbol}均线MACD量比", "technical"),
    )
    for question, section in queries:
        bundle = _call_wenda(mcp.execute, tool_name, question)
        if bundle.get("warning"):
            warnings.append(str(bundle["warning"]))
        parsed = bundle.get("parsed") or {}
        fields = parsed.get("fields") or {}
        for key, value in fields.items():
            if key in _MCP_SKIP_FIELDS:
                continue
            merged_fields[f"{section}.{key}"] = str(value)
            if key not in merged_fields:
                merged_fields[key] = str(value)

    if not merged_fields:
        base["warnings"] = warnings or ["问小达未返回有效走势数据"]
        return base

    return_pct = _extract_return_pct(merged_fields, lookback)
    last_price = _to_float(merged_fields.get("now_price"))
    change_pct = _to_float(merged_fields.get("chg"))
    volatility_pct = _extract_volatility_pct(merged_fields)
    trend_label = TechnicalAnalyzer._describe_trend(return_pct, volatility_pct or 0.0) if return_pct is not None else "—"

    return {
        **base,
        "as_of": datetime.now().strftime("%Y-%m-%d"),
        "return_pct": return_pct,
        "close_end": last_price,
        "change_pct_today": change_pct,
        "volatility_pct": volatility_pct,
        "trend_label": trend_label,
        "pattern_label": "—",
        "ma_alignment": _pick_field_text(merged_fields, ("均线排列", "MA排列", "technical.")),
        "volume_ratio_5d": _to_float(_pick_field_value(merged_fields, ("量比", "volume_ratio"))),
        "mcp_fields": merged_fields,
        "data_quality": "mcp_fallback",
        "sources": ["tdx_mcp"],
        "warnings": warnings,
        "output_guide": ("基于问小达返回字段描述近段历史走势；若缺少精确连涨天数等统计，据已有涨跌幅字段概括，禁止预测未来。"),
        "disclaimer": _DISCLAIMER,
    }


def enrich_local_historical_with_mcp(
    local: dict[str, Any],
    symbol: str,
    *,
    lookback: int,
    mcp: McpBinding,
) -> dict[str, Any]:
    """本地统计为主，问小达补充行情/技术指标（不改变本地 return_pct 等核心字段）。"""
    if mcp.execute is None or not mcp.tool_names:
        return local

    tool_name = _pick_wenda_tool(mcp.tool_names)
    if tool_name is None:
        return local

    item = parse_stock_symbol(symbol)
    if item is None:
        return local

    label = item.name or item.symbol
    warnings = list(local.get("warnings") or [])
    supplement_fields: dict[str, str] = {}

    for question in (
        f"{label}{item.symbol}最新行情涨跌幅",
        f"{label}{item.symbol}MACD KDJ RSI量比",
    ):
        bundle = _call_wenda(mcp.execute, tool_name, question)
        if bundle.get("warning"):
            warnings.append(str(bundle["warning"]))
        fields = (bundle.get("parsed") or {}).get("fields") or {}
        for key, value in fields.items():
            if key in _MCP_SKIP_FIELDS:
                continue
            supplement_fields[key] = str(value)

    if not supplement_fields:
        return local

    enriched = dict(local)
    enriched["mcp_supplement"] = {
        "lookback": lookback,
        "fields": supplement_fields,
        "change_pct_today": _to_float(supplement_fields.get("chg")),
        "last_price": _to_float(supplement_fields.get("now_price")),
    }
    sources = list(enriched.get("sources") or [])
    if "tdx_mcp" not in sources:
        sources.append("tdx_mcp")
    enriched["sources"] = sources
    enriched["warnings"] = list(dict.fromkeys(warnings))
    enriched["data_quality"] = "local_enriched"
    return enriched


def merge_historical_failure(local: dict[str, Any], mcp: dict[str, Any], *, lookback: int) -> dict[str, Any]:
    """本地与 MCP 均不足时的合并错误 payload。"""
    warnings = list(
        dict.fromkeys(
            [
                *(local.get("warnings") or []),
                *(mcp.get("warnings") or []),
            ],
        ),
    )
    if not warnings:
        warnings = ["本地 K 线不足且问小达未返回有效走势数据"]
    return {
        "symbol": local.get("symbol") or mcp.get("symbol"),
        "name": local.get("name") or mcp.get("name"),
        "lookback_requested": lookback,
        "local_available": False,
        "warnings": warnings,
        "sources": [],
        "disclaimer": _DISCLAIMER,
    }


def _extract_return_pct(fields: dict[str, str], lookback: int) -> float | None:
    exact = _pick_return_for_lookback(fields, lookback)
    if exact is not None:
        return exact
    for key, value in fields.items():
        if "涨" not in key and "幅" not in key:
            continue
        if "预测" in key or "目标" in key:
            continue
        parsed = _to_float(value)
        if parsed is not None:
            return round(parsed, 2)
    return None


def _extract_volatility_pct(fields: dict[str, str]) -> float | None:
    for key, value in fields.items():
        if "振幅" in key or "波动" in key:
            parsed = _to_float(value)
            if parsed is not None:
                return round(parsed, 2)
    return None


def _pick_return_for_lookback(fields: dict[str, str], lookback: int) -> float | None:
    best: tuple[int, float] | None = None
    for key, value in fields.items():
        if "涨" not in key and "幅" not in key:
            continue
        if "预测" in key or "目标" in key:
            continue
        parsed = _to_float(value)
        if parsed is None:
            continue
        days = _parse_lookback_from_key(key)
        if days is None:
            continue
        if days == lookback:
            return round(parsed, 2)
        if best is None or abs(days - lookback) < abs(best[0] - lookback):
            best = (days, parsed)
    if best is not None:
        return round(best[1], 2)
    return None


def _parse_lookback_from_key(key: str) -> int | None:
    match = _RETURN_KEY_RE.search(key)
    if match:
        return int(match.group(1))
    match = _NEAR_LOOKBACK_RE.search(key)
    if match:
        return int(match.group(1))
    return None


def _pick_field_value(fields: dict[str, str], keywords: tuple[str, ...]) -> str | None:
    for key, value in fields.items():
        if any(word in key for word in keywords):
            return value
    return None


def _pick_field_text(fields: dict[str, str], keywords: tuple[str, ...]) -> str | None:
    value = _pick_field_value(fields, keywords)
    if value is None:
        return None
    text = str(value).strip()
    return text or None
