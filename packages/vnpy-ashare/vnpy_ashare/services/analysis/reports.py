"""研报获取：通达信 research_reports / 问小达 / Tushare 降级。"""

from __future__ import annotations

import json
from typing import Any

from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.services.analysis.mcp_binding import McpBinding
from vnpy_ashare.services.report_sources import fetch_tushare_reports, report_fallback_enabled
from vnpy_ashare.services.tdx_diagnose import fetch_wenda_research_reports

_REPORT_TOOL_KEYWORDS = ("report", "research", "yanbao", "研报", "rating")
_RESEARCH_REPORTS_TOOL_NAMES = frozenset(
    {"research_reports", "research_report", "stock_research_reports", "tdx_research_reports"},
)
class ReportsFetcher:
    def __init__(self, mcp: McpBinding) -> None:
        self._mcp = mcp

    def fetch_reports(self, item: StockItem) -> dict[str, Any]:
        bundle = self.fetch_tdx_reports(item)
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

    def fetch_tdx_reports(self, item: StockItem) -> dict[str, Any]:
        if self._mcp.execute is None or not self._mcp.tool_names:
            return {
                "reports": [],
                "warnings": ["通达信 MCP 未连接，请在 mcp/mcp.json 配置 tdx-api-key"],
            }

        tool_name = self.pick_research_reports_tool()
        if tool_name is not None:
            bundle = self._call_research_reports_tool(tool_name, item)
            if bundle.get("reports"):
                return bundle
            warnings = list(bundle.get("warnings") or [])
        else:
            warnings = [
                "当前通达信 MCP 未暴露 research_reports 工具（cli tools mcp-list 仅见问小达），"
                "已改经问小达查询近 3 个月研报/评级/目标价。"
            ]

        wenda_bundle = fetch_wenda_research_reports(
            item.vt_symbol,
            mcp_execute=self._mcp.execute,
            tool_names=self._mcp.tool_names,
        )
        if wenda_bundle.get("reports"):
            warnings.extend(wenda_bundle.get("warnings") or [])
            return {
                "reports": wenda_bundle["reports"],
                "raw": wenda_bundle.get("raw_sections"),
                "source": "tdx_mcp",
                "warnings": warnings,
            }

        warnings.extend(wenda_bundle.get("warnings") or [])
        return {"reports": [], "warnings": warnings}

    def pick_research_reports_tool(self) -> str | None:
        for name in self._mcp.tool_names:
            lower = name.lower()
            if lower.startswith("mcp_tdx_"):
                lower = lower.removeprefix("mcp_tdx_")
            if lower in _RESEARCH_REPORTS_TOOL_NAMES:
                return name
        return self.pick_mcp_tool(_REPORT_TOOL_KEYWORDS)

    def _call_research_reports_tool(self, tool_name: str, item: StockItem) -> dict[str, Any]:
        arguments = self.build_research_reports_args(item.vt_symbol, item.symbol)
        try:
            raw_text = self._mcp.execute(tool_name, arguments)
        except Exception as ex:
            return {"reports": [], "warnings": [f"通达信 research_reports 调用失败：{ex}"]}

        if "not found" in raw_text.lower():
            return {
                "reports": [],
                "warnings": [f"通达信 MCP 未注册工具 {tool_name}"],
            }

        parsed = self.parse_mcp_json(raw_text)
        reports = self.normalize_reports(parsed, tool_name)
        return {
            "reports": reports,
            "raw": parsed if isinstance(parsed, dict) else {"text": raw_text[:4000]},
            "source": "tdx_mcp",
            "warnings": [] if reports else [f"通达信 {tool_name} 已调用但未解析到研报条目"],
        }

    @staticmethod
    def build_research_reports_args(vt_symbol: str, symbol: str) -> dict[str, Any]:
        return {
            "code": symbol,
            "stock_code": symbol,
            "symbol": symbol,
            "vt_symbol": vt_symbol,
            "months": 3,
            "period_months": 3,
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
                    "broker": str(row.get("broker") or row.get("org") or row.get("institution") or row.get("org_name") or ""),
                    "date": str(row.get("date") or row.get("publish_date") or row.get("pub_date") or row.get("report_date") or ""),
                    "rating": str(row.get("rating") or row.get("rate") or row.get("invest_rating") or ""),
                    "target_price": str(row.get("target_price") or row.get("target") or row.get("price_target") or ""),
                    "summary": str(row.get("summary") or row.get("abstract") or row.get("content") or row.get("desc") or "")[:2000],
                    "source": "tdx_mcp",
                    "tool": tool_name,
                }
            )
        return reports
