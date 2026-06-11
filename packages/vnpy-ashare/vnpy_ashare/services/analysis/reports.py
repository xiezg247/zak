"""研报获取：通达信 MCP 与 Tushare 降级。"""

from __future__ import annotations

import json
from typing import Any

from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.services.analysis.mcp_binding import McpBinding
from vnpy_ashare.services.report_sources import fetch_tushare_reports, report_fallback_enabled

_REPORT_TOOL_KEYWORDS = ("report", "research", "yanbao", "研报", "rating")
_F10_TOOL_KEYWORDS = ("f10", "fundamental", "financial")


class ReportsFetcher:
    def __init__(self, mcp: McpBinding) -> None:
        self._mcp = mcp

    def fetch_reports(self, item: StockItem) -> dict[str, Any]:
        bundle = self.fetch_tdx_reports(item.vt_symbol, item.symbol)
        if bundle.get("reports"):
            return bundle

        warnings = list(bundle.get("warnings") or [])
        if not report_fallback_enabled():
            return bundle

        fallback = fetch_tushare_reports(item.symbol, item.exchange)
        if fallback.get("reports"):
            warnings.append("通达信 MCP 无研报，已降级使用 Tushare research_report")
            return {
                "reports": fallback["reports"],
                "source": fallback.get("source", "tushare"),
                "warnings": warnings,
            }

        warnings.extend(fallback.get("warnings") or [])
        bundle["warnings"] = warnings
        return bundle

    def fetch_tdx_reports(self, vt_symbol: str, symbol: str) -> dict[str, Any]:
        if self._mcp.execute is None or not self._mcp.tool_names:
            return {
                "reports": [],
                "warnings": ["通达信 MCP 未连接，请在 mcp/mcp.json 配置 tdx-api-key"],
            }

        tool_name = self.pick_mcp_tool(_REPORT_TOOL_KEYWORDS)
        if tool_name is None:
            tool_name = self.pick_mcp_tool(_F10_TOOL_KEYWORDS)
        if tool_name is None:
            return {
                "reports": [],
                "warnings": ["未在通达信 MCP 中发现研报/F10 类工具，请运行 cli.py tools mcp-list 查看"],
            }

        arguments = self.build_mcp_symbol_args(tool_name, vt_symbol, symbol)
        try:
            raw_text = self._mcp.execute(tool_name, arguments)
        except Exception as ex:
            return {"reports": [], "warnings": [f"通达信 MCP 调用失败：{ex}"]}

        parsed = self.parse_mcp_json(raw_text)
        reports = self.normalize_reports(parsed, tool_name)
        return {
            "reports": reports,
            "raw": parsed if isinstance(parsed, dict) else {"text": raw_text[:4000]},
            "source": "tdx_mcp",
            "warnings": [] if reports else ["通达信 MCP 已调用但未解析到研报条目"],
        }

    def pick_mcp_tool(self, keywords: tuple[str, ...]) -> str | None:
        for name in self._mcp.tool_names:
            lower = name.lower()
            if lower.startswith("mcp_tdx_"):
                lower = lower.removeprefix("mcp_tdx_")
            if any(keyword in lower for keyword in keywords):
                return name
        return None

    @staticmethod
    def build_mcp_symbol_args(tool_name: str, vt_symbol: str, symbol: str) -> dict[str, Any]:
        lower = tool_name.lower()
        if "code" in lower or "symbol" in lower or "stock" in lower:
            return {"code": symbol, "symbol": symbol, "stock_code": symbol, "vt_symbol": vt_symbol}
        return {"symbol": vt_symbol, "code": symbol, "stock_code": symbol}

    @staticmethod
    def parse_mcp_json(text: str) -> Any:
        text = text.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}

    def normalize_reports(self, payload: Any, tool_name: str) -> list[dict[str, Any]]:
        rows: list[Any] = []
        if isinstance(payload, list):
            rows = payload
        elif isinstance(payload, dict):
            for key in ("reports", "data", "items", "list", "result"):
                value = payload.get(key)
                if isinstance(value, list):
                    rows = value
                    break
            if not rows and payload.get("text"):
                return [
                    {
                        "title": "通达信 MCP 返回",
                        "summary": str(payload.get("text", ""))[:2000],
                        "source": "tdx_mcp",
                        "tool": tool_name,
                    }
                ]

        reports: list[dict[str, Any]] = []
        for row in rows[:10]:
            if isinstance(row, str):
                reports.append(
                    {
                        "title": row[:120],
                        "summary": row[:2000],
                        "source": "tdx_mcp",
                        "tool": tool_name,
                    }
                )
                continue
            if not isinstance(row, dict):
                continue
            reports.append(
                {
                    "title": str(row.get("title") or row.get("name") or row.get("report_title") or "研报"),
                    "broker": str(row.get("broker") or row.get("org") or row.get("institution") or ""),
                    "date": str(row.get("date") or row.get("publish_date") or row.get("pub_date") or ""),
                    "rating": str(row.get("rating") or row.get("rate") or row.get("invest_rating") or ""),
                    "summary": str(row.get("summary") or row.get("abstract") or row.get("content") or row.get("desc") or "")[:2000],
                    "source": "tdx_mcp",
                    "tool": tool_name,
                }
            )
        return reports
