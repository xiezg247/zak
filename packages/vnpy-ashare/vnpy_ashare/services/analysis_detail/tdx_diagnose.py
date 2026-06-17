"""通达信问小达（tdx_wenda_quotes）个股综合诊断。

经 MCP 并行查询行情 / 技术 / 财务 / 资金流，由 AnalysisService.diagnose 聚合。
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.domain.time.china import format_china_datetime

_MCPExecute = Callable[[str, dict[str, Any]], str]

_WENDA_TOOL_KEYWORDS = ("wenda", "问小达")

_DIAGNOSE_QUERIES: tuple[tuple[str, str], ...] = (
    ("quote", "最新行情涨跌幅成交量"),
    ("technical", "MACD KDJ RSI技术指标"),
    ("fundamental", "市盈率ROE财务指标"),
    ("capital_flow", "主力资金流向"),
)

_HEADER_TAG_RE = re.compile(r"<[^>]+>")
_TRAILING_DATE_RE = re.compile(r"\d{4}\.\d{2}\.\d{2}\d*$")


def run_tdx_diagnose(
    symbol: str,
    *,
    mcp_execute: _MCPExecute | None,
    tool_names: list[str] | None = None,
) -> dict[str, Any]:
    """调用通达信问小达，聚合多维度诊断 JSON。"""
    item = parse_stock_symbol(symbol)
    if item is None:
        return {"error": f"无法解析代码: {symbol}"}

    warnings: list[str] = []
    if mcp_execute is None or not tool_names:
        return {
            "symbol": item.vt_symbol,
            "name": item.name,
            "error": "通达信 MCP 未连接，请在 mcp/mcp.json 配置 tdx-api-key",
            "warnings": ["通达信 MCP 未连接"],
            "sources": [],
            "disclaimer": _DISCLAIMER,
        }

    tool_name = _pick_wenda_tool(tool_names)
    if tool_name is None:
        return {
            "symbol": item.vt_symbol,
            "name": item.name,
            "error": "未找到通达信问小达工具（tdx_wenda_quotes）",
            "warnings": ["请运行 cli.py tools mcp-list 确认 MCP 工具列表"],
            "sources": [],
            "disclaimer": _DISCLAIMER,
        }

    label = item.name or item.symbol
    sections: dict[str, Any] = {}
    for key, suffix in _DIAGNOSE_QUERIES:
        question = f"{label}{item.symbol}{suffix}"
        bundle = _call_wenda(mcp_execute, tool_name, question)
        sections[key] = bundle.get("parsed") or {}
        if bundle.get("warning"):
            warnings.append(str(bundle["warning"]))

    quote = sections.get("quote") or {}
    fields = quote.get("fields") or {}

    return {
        "symbol": item.vt_symbol,
        "name": item.name or str(fields.get("sec_name") or label),
        "as_of": format_china_datetime(),
        "quote": _summarize_quote(quote),
        "technical": _summarize_section(sections.get("technical") or {}, "technical"),
        "fundamental": _summarize_section(sections.get("fundamental") or {}, "fundamental"),
        "capital_flow": _summarize_section(sections.get("capital_flow") or {}, "capital_flow"),
        "raw_sections": sections,
        "warnings": warnings,
        "sources": ["tdx_mcp"],
        "disclaimer": _DISCLAIMER,
    }


_DISCLAIMER = "以上内容来自通达信问小达数据接口，不构成投资建议。"


def _pick_wenda_tool(tool_names: list[str]) -> str | None:
    for name in tool_names:
        lower = name.lower()
        if lower.startswith("mcp_tdx_"):
            lower = lower.removeprefix("mcp_tdx_")
        if any(keyword in lower for keyword in _WENDA_TOOL_KEYWORDS):
            return name
    return None


def _call_wenda(
    mcp_execute: _MCPExecute,
    tool_name: str,
    question: str,
) -> dict[str, Any]:
    try:
        raw_text = mcp_execute(tool_name, {"question": question, "range": "AG"})
    except Exception as ex:
        return {"warning": f"问小达查询失败（{question[:24]}…）：{ex}"}

    parsed = _parse_wenda_table(raw_text)
    if not parsed.get("fields"):
        return {"parsed": parsed, "warning": f"问小达未返回有效数据：{question[:24]}…"}
    return {"parsed": parsed}


def _parse_wenda_table(raw_text: str) -> dict[str, Any]:
    payload = _parse_json(raw_text)
    if not isinstance(payload, dict):
        return {"raw": raw_text[:2000], "fields": {}}

    headers = payload.get("headers") or []
    rows = payload.get("data") or []
    if not rows or not isinstance(rows[0], list):
        return {"headers": headers, "fields": {}, "meta": payload.get("meta")}

    row = rows[0]
    fields: dict[str, str] = {}
    for index, header in enumerate(headers):
        if index >= len(row):
            break
        clean = _clean_header(str(header))
        value = row[index]
        if clean and value not in (None, ""):
            fields[clean] = str(value)

    return {
        "headers": headers,
        "fields": fields,
        "row": row,
        "meta": payload.get("meta"),
    }


def _parse_json(text: str) -> Any:
    text = text.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"text": text}


def _clean_header(header: str) -> str:
    text = _HEADER_TAG_RE.sub("", header)
    text = text.replace("<br>", " ").strip()
    if "#" in text:
        text = text.split("#", 1)[0].strip()
    text = _TRAILING_DATE_RE.sub("", text).strip()
    return text


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if not text or text in ("-", "--"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _summarize_quote(section: dict[str, Any]) -> dict[str, Any]:
    fields = section.get("fields") or {}
    change_pct = _to_float(fields.get("chg"))
    return {
        "last_price": _to_float(fields.get("now_price")),
        "change_pct": change_pct,
        "industry": str(fields.get("所属行业") or "").strip("@"),
        "fields": fields,
    }


def _summarize_section(section: dict[str, Any], kind: str) -> dict[str, Any]:
    fields = section.get("fields") or {}
    summary_fields: dict[str, str] = {}
    for key, value in fields.items():
        if key in {"POS", "market", "sec_code", "sec_name", "now_price", "chg", "所属行业", "show_url"}:
            continue
        summary_fields[key] = value

    payload: dict[str, Any] = {"fields": summary_fields}
    if kind == "technical":
        payload["macd"] = _to_float(summary_fields.get("MACD.MACD"))
        payload["dif"] = _to_float(summary_fields.get("MACD.DIF"))
        payload["dea"] = _to_float(summary_fields.get("MACD.DEA"))
        for key, value in summary_fields.items():
            upper = key.upper()
            if "KDJ.K" in key or key.endswith(".K"):
                payload["kdj_k"] = _to_float(value)
            elif "KDJ.D" in key or (".D" in key and "KDJ" in upper):
                payload["kdj_d"] = _to_float(value)
            elif "KDJ.J" in key or (".J" in key and "KDJ" in upper):
                payload["kdj_j"] = _to_float(value)
            elif "RSI" in upper and payload.get("rsi") is None:
                payload["rsi"] = _to_float(value)
    elif kind == "fundamental":
        for key, value in summary_fields.items():
            lower = key.lower()
            if "市盈" in key or lower.startswith("pe"):
                payload["pe_ttm"] = _to_float(value)
            if "roe" in lower or "净资产收益率" in key:
                payload["roe"] = _to_float(value)
    elif kind == "capital_flow":
        for key, value in summary_fields.items():
            if "主力" in key:
                payload["main_net"] = _to_float(value)
                break
    return payload
