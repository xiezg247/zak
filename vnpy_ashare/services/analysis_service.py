"""股票分析 Service（技术形态、诊断聚合、MCP 研报）。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vnpy_ashare.engine import AshareEngine
    from vnpy_ashare.models import StockItem

from strategies.registry import get_strategy_meta
from strategies.signals import (
    SUPPORTED_SIGNAL_STRATEGIES,
    list_supported_signal_strategies,
    summarize_double_ma_state,
)
from vnpy_ashare.ai.context_store import (
    get_diagnose_result,
    get_screening_results,
    set_diagnose_result,
)
from vnpy_ashare.ai.symbol import parse_stock_symbol
from vnpy_ashare.screener.run_store import get_run
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.services.report_sources import fetch_tushare_reports, report_fallback_enabled
from vnpy_ashare.services.tdx_diagnose import run_tdx_diagnose

_MCPExecute = Callable[[str, dict[str, Any]], str]

_REPORT_TOOL_KEYWORDS = ("report", "research", "yanbao", "研报", "rating")
_F10_TOOL_KEYWORDS = ("f10", "fundamental", "financial")


class AnalysisService(BaseService):
    """聚合本地 K 线与通达信 MCP，产出结构化分析 JSON。"""

    def __init__(self, engine: AshareEngine) -> None:
        super().__init__(engine)
        self._mcp_execute: _MCPExecute | None = None
        self._mcp_tool_names: list[str] = []

    def bind_mcp(
        self,
        execute_fn: _MCPExecute | None,
        tool_names: list[str] | None = None,
    ) -> None:
        self._mcp_execute = execute_fn
        self._mcp_tool_names = list(tool_names or [])

    def technical_snapshot(
        self,
        symbol: str,
        *,
        lookback: int = 60,
        scope: str = "daily",
    ) -> dict[str, Any]:
        item = parse_stock_symbol(symbol)
        if item is None:
            return {"error": f"无法解析代码: {symbol}"}

        lookback = max(5, min(int(lookback or 60), 250))
        bars = self.engine.bar_service.load_bars(
            item.symbol,
            item.exchange,
            scope or "daily",
        )
        warnings: list[str] = []
        if len(bars) < 2:
            return {
                "symbol": item.vt_symbol,
                "scope": scope or "daily",
                "warnings": ["本地暂无足够 K 线，请先在数据管理页下载日 K"],
                "sources": ["bar"],
                "as_of": datetime.now().strftime("%Y-%m-%d"),
            }

        tail = bars[-lookback:] if len(bars) >= lookback else bars
        closes = [bar.close_price for bar in tail]
        volumes = [bar.volume for bar in tail]
        last_close = closes[-1]

        def _ma(window: int) -> float | None:
            if len(closes) < window:
                return None
            segment = closes[-window:]
            return round(sum(segment) / len(segment), 2)

        ma5, ma10, ma20, ma60 = _ma(5), _ma(10), _ma(20), _ma(60)
        ma_alignment = self._describe_ma_alignment(last_close, ma5, ma10, ma20, ma60)

        recent_vol = volumes[-5:] if len(volumes) >= 5 else volumes
        base_vol = volumes[:-5] if len(volumes) > 10 else volumes
        avg_recent = sum(recent_vol) / len(recent_vol) if recent_vol else 0
        avg_base = sum(base_vol) / len(base_vol) if base_vol else avg_recent
        volume_ratio = round(avg_recent / avg_base, 2) if avg_base else None

        period_return = self.engine.bar_service.get_return(
            item.symbol,
            item.exchange,
            scope or "daily",
            lookback_days=min(lookback, 60),
        )

        payload: dict[str, Any] = {
            "symbol": item.vt_symbol,
            "name": item.name,
            "scope": scope or "daily",
            "as_of": tail[-1].datetime.strftime("%Y-%m-%d"),
            "bars_used": len(tail),
            "last_close": round(last_close, 2),
            "ma": {"ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60},
            "ma_alignment": ma_alignment,
            "volume_ratio_5d": volume_ratio,
            "period_return": period_return,
            "sources": ["bar"],
            "warnings": warnings,
        }
        return payload

    def diagnose(
        self,
        symbol: str,
        *,
        lookback: int = 60,
        include_reports: bool = True,
    ) -> dict[str, Any]:
        del lookback  # 诊断改走通达信问小达，不再依赖本地 K 线根数
        return run_tdx_diagnose(
            symbol,
            mcp_execute=self._mcp_execute,
            tool_names=self._mcp_tool_names,
            include_reports=include_reports,
        )

    def _fetch_reports(self, item: StockItem) -> dict[str, Any]:
        bundle = self._fetch_tdx_reports(item.vt_symbol, item.symbol)
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

    def _fetch_tdx_reports(self, vt_symbol: str, symbol: str) -> dict[str, Any]:
        if self._mcp_execute is None or not self._mcp_tool_names:
            return {
                "reports": [],
                "warnings": ["通达信 MCP 未连接，请在 mcp/mcp.json 配置 tdx-api-key"],
            }

        tool_name = self._pick_mcp_tool(_REPORT_TOOL_KEYWORDS)
        if tool_name is None:
            tool_name = self._pick_mcp_tool(_F10_TOOL_KEYWORDS)
        if tool_name is None:
            return {
                "reports": [],
                "warnings": ["未在通达信 MCP 中发现研报/F10 类工具，请运行 scripts/list_mcp_tools.py 查看"],
            }

        arguments = self._build_mcp_symbol_args(tool_name, vt_symbol, symbol)
        try:
            raw_text = self._mcp_execute(tool_name, arguments)
        except Exception as ex:
            return {"reports": [], "warnings": [f"通达信 MCP 调用失败：{ex}"]}

        parsed = self._parse_mcp_json(raw_text)
        reports = self._normalize_reports(parsed, tool_name)
        return {
            "reports": reports,
            "raw": parsed if isinstance(parsed, dict) else {"text": raw_text[:4000]},
            "source": "tdx_mcp",
            "warnings": [] if reports else ["通达信 MCP 已调用但未解析到研报条目"],
        }

    def _pick_mcp_tool(self, keywords: tuple[str, ...]) -> str | None:
        for name in self._mcp_tool_names:
            lower = name.lower()
            if lower.startswith("mcp_tdx_"):
                lower = lower.removeprefix("mcp_tdx_")
            if any(keyword in lower for keyword in keywords):
                return name
        return None

    @staticmethod
    def _build_mcp_symbol_args(tool_name: str, vt_symbol: str, symbol: str) -> dict[str, Any]:
        lower = tool_name.lower()
        if "code" in lower or "symbol" in lower or "stock" in lower:
            return {"code": symbol, "symbol": symbol, "stock_code": symbol, "vt_symbol": vt_symbol}
        return {"symbol": vt_symbol, "code": symbol, "stock_code": symbol}

    @staticmethod
    def _parse_mcp_json(text: str) -> Any:
        text = text.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text}

    def _normalize_reports(self, payload: Any, tool_name: str) -> list[dict[str, Any]]:
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

    @staticmethod
    def _describe_ma_alignment(
        last_close: float,
        ma5: float | None,
        ma10: float | None,
        ma20: float | None,
        ma60: float | None,
    ) -> str:
        if ma5 is None or ma20 is None:
            return "数据不足，无法判断均线排列"
        if ma5 > ma10 > ma20:
            trend = "短期多头排列"
        elif ma5 < ma10 < ma20:
            trend = "短期空头排列"
        else:
            trend = "均线交织"
        above = "站上" if last_close >= ma20 else "跌破"
        detail = f"{trend}，现价{above} MA20"
        if ma60 is not None:
            detail += f"，{'站上' if last_close >= ma60 else '跌破'} MA60"
        return detail

    def strategy_signals(
        self,
        symbol: str,
        *,
        class_name: str = "AshareDoubleMaStrategy",
        lookback: int = 120,
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
    ) -> dict[str, Any]:
        """基于本地 K 线计算策略规则信号（与回测策略逻辑一致）。"""
        item = parse_stock_symbol(symbol)
        if item is None:
            return {"error": f"无法解析代码: {symbol}"}

        meta = get_strategy_meta(class_name)
        if class_name not in SUPPORTED_SIGNAL_STRATEGIES:
            return {
                "error": f"暂不支持策略 {class_name} 的信号计算",
                "supported": list_supported_signal_strategies(),
            }

        lookback = max(30, min(int(lookback or 120), 250))
        fast_window = max(2, int(fast_window or 10))
        slow_window = max(fast_window + 1, int(slow_window or 20))

        bars = self.engine.bar_service.load_bars(
            item.symbol,
            item.exchange,
            scope or "daily",
        )
        warnings: list[str] = []
        if len(bars) < slow_window + 5:
            return {
                "symbol": item.vt_symbol,
                "name": item.name,
                "strategy": class_name,
                "strategy_title": meta.title if meta else class_name,
                "warnings": ["本地 K 线不足，请先在数据管理页下载日 K"],
                "sources": ["bar"],
                "supported": list_supported_signal_strategies(),
            }

        tail = bars[-lookback:] if len(bars) >= lookback else bars
        closes = [bar.close_price for bar in tail]
        dates = [bar.datetime for bar in tail]

        if SUPPORTED_SIGNAL_STRATEGIES[class_name] == "double_ma":
            state = summarize_double_ma_state(
                closes,
                dates,
                fast_window=fast_window,
                slow_window=slow_window,
            )
        else:
            return {"error": f"未实现策略信号: {class_name}"}

        if state.get("error"):
            warnings.append(str(state["error"]))

        return {
            "symbol": item.vt_symbol,
            "name": item.name,
            "strategy": class_name,
            "strategy_title": meta.title if meta else class_name,
            "strategy_summary": meta.summary if meta else "",
            "scope": scope or "daily",
            "bars_used": len(tail),
            "as_of": state.get("as_of"),
            "params": state.get("params"),
            "current": state.get("current"),
            "last_cross": state.get("last_cross"),
            "recent_signals": state.get("recent_signals", []),
            "signal_count": state.get("signal_count", 0),
            "warnings": warnings,
            "sources": ["bar"],
            "disclaimer": "策略信号来自历史规则计算，仅供研究参考，不构成买卖建议。",
        }

    def historical_pattern_summary(
        self,
        symbol: str,
        *,
        lookback: int = 20,
        scope: str = "daily",
    ) -> dict[str, Any]:
        """历史走势统计摘要（描述性，非预测）。"""
        item = parse_stock_symbol(symbol)
        if item is None:
            return {"error": f"无法解析代码: {symbol}"}

        lookback = max(5, min(int(lookback or 20), 120))
        bars = self.engine.bar_service.load_bars(
            item.symbol,
            item.exchange,
            scope or "daily",
        )
        if len(bars) < lookback:
            return {
                "symbol": item.vt_symbol,
                "name": item.name,
                "warnings": ["本地 K 线不足，请先在数据管理页下载日 K"],
                "sources": ["bar"],
            }

        tail = bars[-lookback:]
        closes = [bar.close_price for bar in tail]
        highs = [bar.high_price for bar in tail]
        lows = [bar.low_price for bar in tail]
        first_close = closes[0]
        last_close = closes[-1]
        return_pct = round((last_close - first_close) / first_close * 100, 2) if first_close else 0.0

        daily_changes: list[float] = []
        for index in range(1, len(closes)):
            prev = closes[index - 1]
            if prev:
                daily_changes.append((closes[index] - prev) / prev * 100)

        volatility_pct = 0.0
        if len(daily_changes) >= 2:
            mean_change = sum(daily_changes) / len(daily_changes)
            variance = sum((value - mean_change) ** 2 for value in daily_changes) / len(daily_changes)
            volatility_pct = round(variance**0.5, 2)

        range_pct = 0.0
        if first_close:
            range_pct = round((max(highs) - min(lows)) / first_close * 100, 2)

        up_streak = down_streak = 0
        max_up = max_down = 0
        for change in daily_changes:
            if change > 0:
                up_streak += 1
                down_streak = 0
            elif change < 0:
                down_streak += 1
                up_streak = 0
            else:
                up_streak = down_streak = 0
            max_up = max(max_up, up_streak)
            max_down = max(max_down, down_streak)

        trend_label = self._describe_trend(return_pct, volatility_pct)
        pattern_label = self._describe_pattern(
            return_pct=return_pct,
            volatility_pct=volatility_pct,
            range_pct=range_pct,
            max_up=max_up,
            max_down=max_down,
        )

        technical = self.technical_snapshot(symbol, lookback=min(lookback, 60), scope=scope)

        return {
            "symbol": item.vt_symbol,
            "name": item.name,
            "scope": scope or "daily",
            "lookback_days": len(tail),
            "start": tail[0].datetime.strftime("%Y-%m-%d"),
            "end": tail[-1].datetime.strftime("%Y-%m-%d"),
            "as_of": tail[-1].datetime.strftime("%Y-%m-%d"),
            "return_pct": return_pct,
            "close_start": round(first_close, 2),
            "close_end": round(last_close, 2),
            "high": round(max(highs), 2),
            "low": round(min(lows), 2),
            "range_pct": range_pct,
            "volatility_pct": volatility_pct,
            "max_consecutive_up_days": max_up,
            "max_consecutive_down_days": max_down,
            "trend_label": trend_label,
            "pattern_label": pattern_label,
            "ma_alignment": technical.get("ma_alignment"),
            "volume_ratio_5d": technical.get("volume_ratio_5d"),
            "warnings": list(technical.get("warnings") or []),
            "sources": ["bar"],
            "disclaimer": "以上均为历史区间统计，不代表对未来走势的判断或预测。",
        }

    @staticmethod
    def _describe_trend(return_pct: float, volatility_pct: float) -> str:
        if return_pct >= 5:
            base = "区间明显上行"
        elif return_pct <= -5:
            base = "区间明显下行"
        elif return_pct >= 1:
            base = "区间温和上行"
        elif return_pct <= -1:
            base = "区间温和下行"
        else:
            base = "区间横盘震荡"
        if volatility_pct >= 3:
            return f"{base}，波动偏大"
        if volatility_pct <= 1:
            return f"{base}，波动偏低"
        return base

    @staticmethod
    def _describe_pattern(
        *,
        return_pct: float,
        volatility_pct: float,
        range_pct: float,
        max_up: int,
        max_down: int,
    ) -> str:
        parts: list[str] = []
        if abs(return_pct) < 2 and range_pct < 8:
            parts.append("窄幅震荡")
        elif return_pct > 0 and max_up >= 3:
            parts.append("阶段性连阳")
        elif return_pct < 0 and max_down >= 3:
            parts.append("阶段性连阴")
        elif volatility_pct >= 3.5:
            parts.append("高波动")
        else:
            parts.append("常规波动")
        if return_pct > 2:
            parts.append("重心上移")
        elif return_pct < -2:
            parts.append("重心下移")
        return " · ".join(parts)

    def build_screening_context(
        self,
        *,
        run_id: str | None = None,
        batch_top_n: int = 0,
    ) -> dict[str, Any]:
        """读取选股结果；可选历史 run_id 与批量技术面快照。"""
        screening_svc = getattr(self.engine, "screening_service", None)

        if run_id:
            record = get_run(run_id.strip())
            if record is None:
                return {"message": f"选股历史 run 不存在：{run_id}"}
            condition = record.condition
            updated_at = record.created_at
            rows = list(record.rows)
            source = "history_run"
            run_meta = {
                "run_id": record.id,
                "source": record.source,
                "total_scanned": record.total_scanned,
            }
        else:
            ctx = screening_svc.get_screening_results() if screening_svc is not None else get_screening_results()
            if ctx is None:
                return {
                    "message": "暂无选股结果，请用户先在「选股」页运行方案，或提供 run_id",
                }
            condition = ctx.condition
            updated_at = ctx.updated_at
            rows = list(ctx.rows)
            source = "session"
            run_meta = {}

        preview = []
        for row in rows[:20]:
            preview.append(
                {
                    "vt_symbol": row.get("vt_symbol", ""),
                    "name": row.get("name", ""),
                    "change_pct": row.get("change_pct"),
                    "pe_ttm": row.get("pe_ttm"),
                    "net_mf_amount": row.get("net_mf_amount"),
                }
            )

        payload: dict[str, Any] = {
            "condition": condition,
            "count": len(rows),
            "updated_at": updated_at,
            "preview": preview,
            "source": source,
            **run_meta,
        }

        batch_n = max(0, min(int(batch_top_n or 0), 10))
        if batch_n > 0:
            snapshots: list[dict[str, Any]] = []
            for row in rows[:batch_n]:
                symbol = str(row.get("vt_symbol") or row.get("symbol") or "").strip()
                if not symbol:
                    continue
                snap = self.technical_snapshot(symbol, lookback=20)
                snapshots.append(
                    {
                        "vt_symbol": snap.get("symbol", symbol),
                        "name": row.get("name", snap.get("name", "")),
                        "ma_alignment": snap.get("ma_alignment"),
                        "last_close": snap.get("last_close"),
                        "period_return": snap.get("period_return"),
                        "warnings": snap.get("warnings") or [],
                    }
                )
            payload["batch_snapshots"] = snapshots
            payload["batch_top_n"] = batch_n

        return payload

    def set_diagnose_result(self, payload: dict[str, Any] | None) -> None:
        """写入最近一次诊断结果，供 AI Skill ``get_diagnose_context`` 读取。"""
        set_diagnose_result(payload)

    def get_diagnose_result(self) -> dict[str, Any] | None:
        return get_diagnose_result()
