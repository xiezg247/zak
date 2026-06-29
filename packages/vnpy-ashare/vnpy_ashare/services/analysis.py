"""股票分析 Service（技术形态、诊断聚合）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy_ashare.config.preferences.watchlist_signal import SIGNAL_LOOKBACK_BARS, load_signal_panel_symbols
from vnpy_ashare.integrations.tickflow.quotes import fetch_quotes_from_tickflow
from vnpy_ashare.quotes.analysis.entry_mode import evaluate_entry_mode_for_symbol
from vnpy_ashare.quotes.analysis.leader_tier import explain_leader_tier_for_symbol
from vnpy_ashare.services.stock.news import get_stock_news_for_symbol
from vnpy_ashare.services.stock.regulatory_deviation import assess_regulatory_deviation_for_symbol

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine

from vnpy_ashare.ai.context.quote.format import format_quote_summary
from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.domain.trading.signal_snapshot import (
    SignalSnapshot,
    signal_missing_kline,
    signal_snapshot_to_dict,
)
from vnpy_ashare.domain.trading.stock_continuation import StockContinuationSnapshot
from vnpy_ashare.services.analysis_detail.diagnose import DiagnoseAnalyzer
from vnpy_ashare.services.analysis_detail.historical_mcp import (
    enrich_local_historical_with_mcp,
    fetch_historical_pattern_mcp,
    local_historical_sufficient,
    merge_historical_failure,
)
from vnpy_ashare.services.analysis_detail.mcp_binding import McpBinding, McpExecute
from vnpy_ashare.services.analysis_detail.risk_metrics import (
    benchmark_symbol_exchange,
    compute_beta_vs_hs300,
    fetch_market_sentiment,
)
from vnpy_ashare.services.analysis_detail.team_facts import build_financial_extras, prefetch_team_facts
from vnpy_ashare.services.analysis_detail.technical.analyzer import TechnicalAnalyzer
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.services.signals.stock_continuation import (
    build_continuation_batch,
    continuation_snapshot_to_dict,
    format_continuation_context_extra,
    format_signal_panel_context_extra,
)


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
        """财务深度分析：本地财报快照 + Tushare daily_basic 估值 + K 线覆盖。"""
        item = parse_stock_symbol(symbol)
        if item is None:
            return {"error": f"无法解析代码: {symbol}"}

        overview = self.engine.bar_service.get_overview(item.symbol, item.exchange, "daily")
        return_info = self.engine.bar_service.get_return(item.symbol, item.exchange, "daily", lookback_days=60)
        extras = build_financial_extras(item.ts_code, item.vt_symbol)
        from vnpy_ashare.services.stock.valuation_chart import build_valuation_chart_series

        valuation_series = build_valuation_chart_series(item.ts_code)

        return {
            "symbol": item.vt_symbol,
            "name": item.name,
            "provider": "zak-financial-v2",
            "bar_count": overview.count if overview else 0,
            "start_date": overview.start.strftime("%Y-%m-%d") if overview and overview.start else None,
            "end_date": overview.end.strftime("%Y-%m-%d") if overview and overview.end else None,
            "return_pct_60d": return_info.get("return_pct"),
            "valuation_pe_series": valuation_series["pe_ttm"],
            "valuation_pb_series": valuation_series["pb"],
            **extras,
        }

    def prefetch_team_facts(self, symbol: str) -> dict[str, Any]:
        """并行预取团队分析三维度事实数据（无 LLM）。"""
        return prefetch_team_facts(self, symbol)

    def _compute_bar_risk_metrics(
        self,
        symbol: str,
        exchange,
        *,
        lookback: int = 60,
    ) -> dict[str, Any]:
        """基于本地日 K 计算波动率、最大回撤与流动性。"""
        lookback = max(5, min(int(lookback or 60), 250))
        bars = self.engine.bar_service.load_bars(symbol, exchange, "daily")
        if len(bars) < 5:
            return {}

        tail = bars[-lookback:] if len(bars) >= lookback else bars
        closes = [bar.close_price for bar in tail]
        volumes = [bar.volume for bar in tail]

        daily_changes: list[float] = []
        for index in range(1, len(closes)):
            prev = closes[index - 1]
            if prev:
                daily_changes.append((closes[index] - prev) / prev)

        volatility_annualized_pct = None
        if len(daily_changes) >= 2:
            mean_change = sum(daily_changes) / len(daily_changes)
            variance = sum((value - mean_change) ** 2 for value in daily_changes) / len(daily_changes)
            volatility_annualized_pct = round((variance**0.5) * (252**0.5) * 100, 2)

        peak = closes[0]
        max_drawdown_pct = 0.0
        for close in closes:
            if close > peak:
                peak = close
            if peak:
                drawdown = (peak - close) / peak * 100
                max_drawdown_pct = max(max_drawdown_pct, drawdown)
        max_drawdown_pct = round(max_drawdown_pct, 2)

        avg_volume = round(sum(volumes) / len(volumes)) if volumes else None

        return {
            "volatility_annualized_pct": volatility_annualized_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "avg_volume": avg_volume,
            "bars_used": len(tail),
        }

    def analyze_risk(self, symbol: str) -> dict[str, Any]:
        """风险分析：波动率、最大回撤、区间收益与流动性。"""
        item = parse_stock_symbol(symbol)
        if item is None:
            return {"error": f"无法解析代码: {symbol}"}

        return_info = self.engine.bar_service.get_return(item.symbol, item.exchange, "daily", lookback_days=60)
        overview = self.engine.bar_service.get_overview(item.symbol, item.exchange, "daily")
        metrics = self._compute_bar_risk_metrics(item.symbol, item.exchange)

        bench_symbol, bench_exchange = benchmark_symbol_exchange()
        stock_bars = self.engine.bar_service.load_bars(item.symbol, item.exchange, "daily")
        bench_bars = self.engine.bar_service.load_bars(bench_symbol, bench_exchange, "daily")
        beta = compute_beta_vs_hs300(stock_bars, bench_bars)
        market_sentiment = fetch_market_sentiment()

        has_vol = metrics.get("volatility_annualized_pct") is not None
        has_dd = metrics.get("max_drawdown_pct") is not None
        has_liq = metrics.get("avg_volume") is not None
        has_beta = beta is not None
        has_sentiment = market_sentiment is not None

        note_parts = ["波动率/回撤/Beta 基于本地日 K 与沪深300对齐计算"]
        if has_sentiment:
            note_parts.append("恐贪指数来自 SentimentService")

        return {
            "symbol": item.vt_symbol,
            "name": item.name,
            "provider": "zak-risk-v2",
            "bar_count": overview.count if overview else 0,
            "return_pct_60d": return_info.get("return_pct"),
            "lookback_days": return_info.get("lookback_days"),
            "start_date": return_info.get("start"),
            "end_date": return_info.get("end"),
            "volatility_annualized_pct": metrics.get("volatility_annualized_pct"),
            "max_drawdown_pct": metrics.get("max_drawdown_pct"),
            "avg_volume": metrics.get("avg_volume"),
            "beta": beta,
            "market_sentiment": market_sentiment,
            "data_availability": {
                "volatility": has_vol,
                "max_drawdown": has_dd,
                "beta": has_beta,
                "liquidity": has_liq,
                "fear_greed": has_sentiment,
            },
            "note": "；".join(note_parts) + "。",
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
        lookback: int = SIGNAL_LOOKBACK_BARS,
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
        lookback: int = SIGNAL_LOOKBACK_BARS,
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
        lookback: int = SIGNAL_LOOKBACK_BARS,
        fast_window: int = 10,
        slow_window: int = 20,
        scope: str = "daily",
        max_workers: int | None = None,
    ) -> dict[str, SignalSnapshot]:
        return self._technical.batch_strategy_signals(
            symbols,
            class_name=class_name,
            lookback=lookback,
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
            max_workers=max_workers,
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

    def enrich_continuation_batch(
        self,
        vt_symbols: list[str],
        signal_cache: dict[str, SignalSnapshot],
        *,
        main_engine=None,
    ) -> dict[str, StockContinuationSnapshot]:
        """信号区：批量构建个股延续快照（价量 + 可选资金/板块环境）。"""
        return build_continuation_batch(vt_symbols, signal_cache, main_engine=main_engine)

    def list_watchlist_signal_panel(
        self,
        *,
        class_name: str = "AshareDoubleMaStrategy",
        fast_window: int = 10,
        slow_window: int = 20,
        include_live_quote: bool = False,
    ) -> dict[str, Any]:
        """批量返回信号区名单的策略快照（可选附带实时行情修饰）。"""

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
        continuations = build_continuation_batch(symbols, snaps, main_engine=self.main_engine)

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
            continuation = continuations.get(vt_symbol)
            if continuation is not None:
                entry["continuation"] = continuation_snapshot_to_dict(continuation)
                entry["continuation_context"] = format_continuation_context_extra(continuation)
            item = parse_stock_symbol(vt_symbol)
            if item is not None:
                entry["name"] = item.name
                quote = quote_map.get(item.tickflow_symbol)
                if include_live_quote and quote is not None and quote.last_price > 0:
                    entry["quote_summary"] = format_quote_summary(quote)
                    entry["live_context"] = format_signal_panel_context_extra(
                        snap,
                        continuation,
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

    def evaluate_entry_mode(self, symbol: str) -> dict[str, Any]:

        return evaluate_entry_mode_for_symbol(symbol)

    def explain_leader_tier(self, symbol: str) -> dict[str, Any]:
        return explain_leader_tier_for_symbol(symbol)

    def assess_regulatory_deviation(self, symbol: str) -> dict[str, Any]:
        return assess_regulatory_deviation_for_symbol(symbol)

    def get_stock_news(self, symbol: str, *, limit: int = 20) -> dict[str, Any]:
        return get_stock_news_for_symbol(symbol, limit=limit)
