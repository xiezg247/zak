"""股票分析 Service（技术形态、诊断聚合）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine

from vnpy_ashare.ai.context.quote import format_quote_summary
from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.domain.signal_snapshot import (
    SignalSnapshot,
    signal_missing_kline,
    signal_snapshot_to_dict,
)
from vnpy_ashare.services.analysis.diagnose import DiagnoseAnalyzer
from vnpy_ashare.services.analysis.historical_mcp import (
    enrich_local_historical_with_mcp,
    fetch_historical_pattern_mcp,
    local_historical_sufficient,
    merge_historical_failure,
)
from vnpy_ashare.services.analysis.mcp_binding import McpBinding, McpExecute
from vnpy_ashare.services.analysis.technical import TechnicalAnalyzer
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.services.signals import format_signal_context_extra


class AnalysisService(BaseService):
    """聚合本地 K 线与通达信 MCP，产出结构化分析 JSON。"""

    def __init__(self, engine: AshareEngine) -> None:
        super().__init__(engine)
        self._mcp = McpBinding()
        self._technical = TechnicalAnalyzer(engine)
        self._diagnose = DiagnoseAnalyzer(self._mcp)

    def bind_mcp(
        self,
        execute_fn: McpExecute | None,
        tool_names: list[str] | None = None,
    ) -> None:
        self._mcp.execute = execute_fn
        self._mcp.tool_names = list(tool_names or [])

    def technical_snapshot(
        self,
        symbol: str,
        *,
        lookback: int = 60,
        scope: str = "daily",
    ) -> dict[str, Any]:
        return self._technical.technical_snapshot(symbol, lookback=lookback, scope=scope)

    def diagnose(
        self,
        symbol: str,
        *,
        lookback: int = 60,
    ) -> dict[str, Any]:
        return self._diagnose.diagnose(symbol, lookback=lookback)

    def analyze_financial(self, symbol: str) -> dict[str, Any]:
        """财务深度分析：PE/ROE/毛利率/净利润同比/营收CAGR/估值对比。

        注：首期返回基础框架结构；后续接入 Tushare 财务接口补全。
        """
        try:
            item = parse_stock_symbol(symbol)
        except Exception:
            item = None

        name = item.name if item else symbol
        exchange = item.exchange if item else None
        overview = self._engine.bar_service.get_overview(
            item.symbol, exchange, "daily"
        ) if item and exchange else None

        return {
            "symbol": symbol,
            "name": name,
            "provider": "zak-financial-v1",
            "bar_count": overview.count if overview else 0,
            "start_date": overview.start.strftime("%Y-%m-%d") if overview and overview.start else None,
            "end_date": overview.end.strftime("%Y-%m-%d") if overview and overview.end else None,
            "data_availability": {
                "roe": False,
                "gross_margin": False,
                "net_profit_yoy": False,
                "revenue_cagr_3y": False,
                "debt_ratio": False,
                "current_ratio": False,
            },
            "note": "财务详细数据依赖 Tushare 接口，当前返回基础 K 线覆盖信息。",
        }

    def analyze_risk(self, symbol: str) -> dict[str, Any]:
        """风险分析：波动率/回撤/Beta/流动性。

        注：首期从 K 线数据计算基础波动率和回撤；Beta 后续补全。
        """
        try:
            item = parse_stock_symbol(symbol)
        except Exception:
            item = None

        name = item.name if item else symbol
        exchange = item.exchange if item else None

        return_info = {}
        if item and exchange:
            return_info = self._engine.bar_service.get_return(
                item.symbol, exchange, "daily", lookback_days=60
            )

        overview = self._engine.bar_service.get_overview(
            item.symbol, exchange, "daily"
        ) if item and exchange else None

        return {
            "symbol": symbol,
            "name": name,
            "provider": "zak-risk-v1",
            "bar_count": overview.count if overview else 0,
            "return_pct": return_info.get("return_pct"),
            "lookback_days": return_info.get("lookback_days"),
            "start_date": return_info.get("start"),
            "end_date": return_info.get("end"),
            "data_availability": {
                "volatility": False,
                "max_drawdown": False,
                "beta": False,
                "liquidity": False,
            },
            "note": "风险指标依赖 K 线计算，当前返回区间收益率与 K 线覆盖。",
        }

    def analyze_strategy(self, symbol: str) -> dict[str, Any]:
        """策略适配分析：复用 technical_snapshot + strategy_signals。"""
        technical = self.technical_snapshot(symbol)
        signals = self.strategy_signals(symbol)

        return {
            "symbol": symbol,
            "provider": "zak-strategy-v1",
            "technical": technical,
            "strategy_signals": signals,
        }

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
        return self._technical.strategy_signals(
            symbol,
            class_name=class_name,
            lookback=lookback,
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
        )

    def signal_snapshot(
        self,
        symbol: str,
        *,
        class_name: str = "AshareDoubleMaStrategy",
        lookback: int = 120,
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
    ) -> SignalSnapshot | None:
        return self._technical.signal_snapshot(
            symbol,
            class_name=class_name,
            lookback=lookback,
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
        )

    def batch_strategy_signals(
        self,
        symbols: list[str],
        *,
        class_name: str = "AshareDoubleMaStrategy",
        lookback: int = 120,
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
    ) -> dict[str, SignalSnapshot]:
        return self._technical.batch_strategy_signals(
            symbols,
            class_name=class_name,
            lookback=lookback,
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
        )

    def enrich_relative_index(self, snapshot: SignalSnapshot) -> SignalSnapshot:
        """补算缺失的 relative_index_pct（单票）。"""
        return self._technical.enrich_relative_index(snapshot)

    def enrich_relative_index_batch(
        self,
        snapshots: dict[str, SignalSnapshot],
    ) -> dict[str, SignalSnapshot]:
        """补算缺失的 relative_index_pct（磁盘旧快照或基准源切换后）。"""
        return self._technical.enrich_relative_index_batch(snapshots)

    def list_watchlist_signal_panel(
        self,
        *,
        class_name: str = "AshareDoubleMaStrategy",
        fast_window: int = 10,
        slow_window: int = 20,
        include_live_quote: bool = False,
    ) -> dict[str, Any]:
        """批量返回信号区名单的策略快照（可选附带实时行情修饰）。"""
        from vnpy_ashare.config.preferences import load_signal_panel_symbols
        from vnpy_ashare.integrations.tickflow import fetch_quotes_from_tickflow

        symbols = load_signal_panel_symbols()
        if not symbols:
            return {
                "symbols": [],
                "items": [],
                "class_name": class_name,
                "fast_window": int(fast_window or 10),
                "slow_window": int(slow_window or 20),
                "warnings": ["信号区暂无监控标的"],
            }

        fast = max(2, int(fast_window or 10))
        slow = max(fast + 1, int(slow_window or 20))
        snaps = self.batch_strategy_signals(
            symbols,
            class_name=class_name or "AshareDoubleMaStrategy",
            fast_window=fast,
            slow_window=slow,
        )

        quote_map: dict[str, Any] = {}
        stock_items = []
        for vt_symbol in symbols:
            item = parse_stock_symbol(vt_symbol)
            if item is not None:
                stock_items.append(item)
        if include_live_quote and stock_items:
            try:
                quote_map = fetch_quotes_from_tickflow(stock_items)
            except Exception:
                quote_map = {}

        stats = {"buy": 0, "sell": 0, "hold": 0, "na": 0, "missing_kline": 0}
        items: list[dict[str, Any]] = []
        for vt_symbol in symbols:
            snap = snaps.get(vt_symbol)
            if snap is None:
                continue
            if signal_missing_kline(snap):
                stats["missing_kline"] += 1
            elif snap.signal in stats:
                stats[snap.signal] += 1

            entry: dict[str, Any] = {
                "vt_symbol": vt_symbol,
                "snapshot": signal_snapshot_to_dict(snap),
            }
            item = parse_stock_symbol(vt_symbol)
            if item is not None:
                entry["name"] = item.name
                quote = quote_map.get(item.tickflow_symbol)
                if include_live_quote and quote is not None and quote.last_price > 0:
                    entry["quote_summary"] = format_quote_summary(quote)
                    entry["live_context"] = format_signal_context_extra(
                        snap,
                        quote=quote,
                        fast_window=fast,
                        slow_window=slow,
                    )
            items.append(entry)

        return {
            "class_name": class_name or "AshareDoubleMaStrategy",
            "fast_window": fast,
            "slow_window": slow,
            "symbols": symbols,
            "count": len(symbols),
            "stats": stats,
            "items": items,
            "disclaimer": "规则计算结果，仅供研究，不构成买卖建议",
        }

    def historical_pattern_summary(
        self,
        symbol: str,
        *,
        lookback: int = 20,
        scope: str = "daily",
    ) -> dict[str, Any]:
        local = self._technical.historical_pattern_summary(symbol, lookback=lookback, scope=scope)
        if local_historical_sufficient(local):
            return enrich_local_historical_with_mcp(
                local,
                symbol,
                lookback=lookback,
                mcp=self._mcp,
            )

        mcp_result = fetch_historical_pattern_mcp(symbol, lookback=lookback, mcp=self._mcp)
        if local_historical_sufficient(mcp_result):
            return mcp_result

        return merge_historical_failure(local, mcp_result, lookback=lookback)

    def trend_scenario_summary(
        self,
        symbol: str,
        *,
        horizon_days: int = 5,
        lookback: int = 60,
        class_name: str = "AshareDoubleMaStrategy",
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
    ) -> dict[str, Any]:
        return self._technical.trend_scenario_summary(
            symbol,
            horizon_days=horizon_days,
            lookback=lookback,
            class_name=class_name,
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
        )

    def build_screening_context(
        self,
        *,
        run_id: str | None = None,
        batch_top_n: int = 0,
    ) -> dict[str, Any]:
        return self._technical.build_screening_context(run_id=run_id, batch_top_n=batch_top_n)

    def build_screening_explanation(
        self,
        *,
        run_id: str | None = None,
        batch_top_n: int = 5,
    ) -> dict[str, Any]:
        return self._technical.build_screening_explanation(run_id=run_id, batch_top_n=batch_top_n)

    def set_diagnose_result(self, payload: dict[str, Any] | None) -> None:
        """写入最近一次诊断结果，供 AI Skill ``get_diagnose_context`` 读取。"""
        self._diagnose.set_diagnose_result(payload)

    def get_diagnose_result(self) -> dict[str, Any] | None:
        return self._diagnose.get_diagnose_result()
