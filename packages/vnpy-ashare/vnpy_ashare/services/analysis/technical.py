"""本地 K 线技术面、策略信号与选股解读编排。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine

from strategies.registry import get_strategy_meta
from strategies.signals import (
    SUPPORTED_SIGNAL_STRATEGIES,
    build_signal_payload_for_strategy,
    list_supported_signal_strategies,
    summarize_double_ma_state,
    summarize_short_breakout_state,
    summarize_swing_ma_state,
    summarize_trend_ma_state,
)
from vnpy_ashare.ai.context import get_screening_results, parse_stock_symbol
from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.data.pattern_bars import pattern_load_max_workers
from vnpy_ashare.domain.signal_benchmark import compute_relative_index_excess, resolve_benchmark_return_pct
from vnpy_ashare.domain.signal_snapshot import (
    SIGNAL_BENCHMARK_LOOKBACK,
    SignalSnapshot,
)
from vnpy_ashare.screener.run.run_diff import compute_run_diff
from vnpy_ashare.screener.run.run_store import find_previous_run_by_recipe, get_run
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution


class TechnicalAnalyzer:
    def __init__(self, engine: AshareEngine) -> None:
        self._engine = engine
        self._benchmark_return_cache_key: int | None = None
        self._benchmark_return_cache_val: float | None = None

    def reset_benchmark_cache(self) -> None:
        self._benchmark_return_cache_key = None
        self._benchmark_return_cache_val = None

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
        bars = self._engine.bar_service.load_bars(
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

        period_return = self._engine.bar_service.get_return(
            item.symbol,
            item.exchange,
            scope or "daily",
            lookback_days=min(lookback, 60),
        )

        return {
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

        bars = self._engine.bar_service.load_bars(
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
        highs = [bar.high_price for bar in tail]
        volumes = [float(bar.volume) for bar in tail]
        dates = [bar.datetime for bar in tail]

        kind = SUPPORTED_SIGNAL_STRATEGIES[class_name]
        if kind == "double_ma":
            state = summarize_double_ma_state(
                closes,
                dates,
                fast_window=fast_window,
                slow_window=slow_window,
            )
        elif kind == "short_breakout":
            state = summarize_short_breakout_state(
                closes,
                highs,
                dates,
                volumes,
                fast_window=fast_window,
                slow_window=slow_window,
            )
        elif kind == "swing_ma":
            state = summarize_swing_ma_state(
                closes,
                dates,
                volumes,
                lows=[bar.low_price for bar in tail],
                fast_window=fast_window,
                slow_window=slow_window,
            )
        elif kind == "trend_ma":
            state = summarize_trend_ma_state(
                closes,
                dates,
                highs,
                [bar.low_price for bar in tail],
                fast_window=fast_window,
                slow_window=slow_window,
            )
        else:
            return {"error": f"未实现策略信号: {class_name}"}

        if state.get("error"):
            warnings.append(str(state["error"]))

        result: dict[str, Any] = {
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
            "warnings": warnings,
            "sources": ["bar"],
        }
        if kind == "double_ma":
            result["recent_signals"] = state.get("recent_signals", [])
            result["signal_count"] = state.get("signal_count", 0)
        elif kind == "short_breakout":
            result["last_breakout"] = state.get("last_breakout")
            result["recent_breakouts"] = state.get("recent_breakouts", [])
            result["breakout_count"] = state.get("breakout_count", 0)
        elif kind == "swing_ma":
            result["last_entry"] = state.get("last_entry")
            result["recent_entries"] = state.get("recent_entries", [])
            result["entry_count"] = state.get("entry_count", 0)
            result["recent_signals"] = state.get("recent_signals", [])
            result["signal_count"] = state.get("signal_count", 0)
        elif kind == "trend_ma":
            result["recent_signals"] = state.get("recent_signals", [])
            result["signal_count"] = state.get("signal_count", 0)
            result["adx"] = (state.get("current") or {}).get("adx")
        return result

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
        """单标的策略信号快照（供自选页表格）。"""
        payload = self._build_signal_payload(
            symbol,
            class_name=class_name,
            lookback=lookback,
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
        )
        if payload is None:
            return None
        return self._payload_to_signal_snapshot(payload)

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
        """批量计算策略信号（自选池 Worker 调用）。"""
        if not symbols:
            return {}

        self.reset_benchmark_cache()
        payload_kwargs = {
            "class_name": class_name,
            "lookback": lookback,
            "fast_window": fast_window,
            "slow_window": slow_window,
            "scope": scope,
        }

        def worker(symbol: str) -> tuple[str, SignalSnapshot] | None:
            payload = self._build_signal_payload(symbol, **payload_kwargs)
            if payload is None:
                return None
            return payload["vt_symbol"], self._payload_to_signal_snapshot(payload)

        workers = pattern_load_max_workers(item_count=len(symbols))
        pairs = run_parallel_map(symbols, worker, max_workers=workers)
        results: dict[str, SignalSnapshot] = {}
        for item in pairs:
            if item is None:
                continue
            vt_symbol, snapshot = item
            results[vt_symbol] = snapshot
        return results

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
        bars = self._engine.bar_service.load_bars(
            item.symbol,
            item.exchange,
            scope or "daily",
        )
        if len(bars) < lookback:
            return {
                "symbol": item.vt_symbol,
                "name": item.name,
                "lookback_requested": lookback,
                "local_available": False,
                "warnings": ["本地 K 线不足，将尝试问小达 MCP 兜底"],
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

        if up_streak > 0:
            current_streak_direction = "up"
            current_streak_days = up_streak
        elif down_streak > 0:
            current_streak_direction = "down"
            current_streak_days = down_streak
        else:
            current_streak_direction = "flat"
            current_streak_days = 0

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
            "current_streak_days": current_streak_days,
            "current_streak_direction": current_streak_direction,
            "trend_label": trend_label,
            "pattern_label": pattern_label,
            "ma_alignment": technical.get("ma_alignment"),
            "volume_ratio_5d": technical.get("volume_ratio_5d"),
            "warnings": list(technical.get("warnings") or []),
            "local_available": True,
            "data_quality": "local",
            "sources": ["bar"],
            "disclaimer": "以上均为历史区间统计，不代表对未来走势的判断或预测。",
        }

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
        """本地走势情景摘要：技术面、结构锚点与统计参考带，供 LLM 做情景分析（非确定性预测）。"""
        item = parse_stock_symbol(symbol)
        if item is None:
            return {"error": f"无法解析代码: {symbol}"}

        horizon_days = max(1, min(int(horizon_days or 5), 20))
        lookback = max(20, min(int(lookback or 60), 120))
        fast_window = max(2, int(fast_window or 10))
        slow_window = max(fast_window + 1, int(slow_window or 20))

        technical = self.technical_snapshot(symbol, lookback=lookback, scope=scope)
        warnings: list[str] = list(technical.get("warnings") or [])
        if technical.get("error"):
            return {"error": str(technical["error"])}

        momentum_lookback = max(horizon_days, min(horizon_days * 4, 20))
        momentum = self.historical_pattern_summary(
            symbol,
            lookback=momentum_lookback,
            scope=scope,
        )
        warnings.extend(momentum.get("warnings") or [])

        payload = self._build_signal_payload(
            symbol,
            class_name=class_name,
            lookback=max(lookback, 120),
            fast_window=fast_window,
            slow_window=slow_window,
            scope=scope,
        )
        structure: dict[str, Any] = {
            "strategy": class_name,
            "fast_window": fast_window,
            "slow_window": slow_window,
            "signal": "na",
            "signal_label": "—",
            "ref_buy_price": None,
            "ref_sell_price": None,
            "dist_buy_pct": None,
            "dist_sell_pct": None,
            "fast_ma": None,
            "slow_ma": None,
            "reason_summary": "",
        }
        if payload:
            last_close = technical.get("last_close") or payload.get("last_close")
            ref_buy = payload.get("ref_buy_price")
            ref_sell = payload.get("ref_sell_price")
            dist_buy = None
            dist_sell = None
            if last_close and ref_buy:
                dist_buy = round((float(last_close) - float(ref_buy)) / float(ref_buy) * 100, 2)
            if last_close and ref_sell:
                dist_sell = round((float(ref_sell) - float(last_close)) / float(last_close) * 100, 2)
            structure.update(
                {
                    "signal": payload.get("signal") or "na",
                    "signal_label": payload.get("signal_label") or "—",
                    "ref_buy_price": ref_buy,
                    "ref_sell_price": ref_sell,
                    "dist_buy_pct": dist_buy,
                    "dist_sell_pct": dist_sell,
                    "fast_ma": payload.get("fast_ma"),
                    "slow_ma": payload.get("slow_ma"),
                    "reason_summary": payload.get("reason_summary") or "",
                }
            )
            warnings.extend(payload.get("warnings") or ())

        last_close = technical.get("last_close")
        reference_bands: dict[str, Any] | None = None
        if last_close:
            daily_vol = self._estimate_daily_volatility_pct(symbol, scope=scope, window=20)
            if daily_vol is not None:
                move_pct = round(daily_vol * (horizon_days**0.5), 2)
                reference_bands = {
                    "method": "historical_daily_volatility_1sigma",
                    "horizon_days": horizon_days,
                    "base_price": last_close,
                    "move_pct_1sigma": move_pct,
                    "upper_1sigma": round(float(last_close) * (1 + move_pct / 100), 2),
                    "lower_1sigma": round(float(last_close) * (1 - move_pct / 100), 2),
                    "note": "基于历史日波动率的统计参考区间，非预测目标价或买卖价",
                }

        direction_hints = self._build_direction_hints(
            ma_alignment=str(technical.get("ma_alignment") or ""),
            structure=structure,
            momentum_return_pct=momentum.get("return_pct"),
            volume_ratio=technical.get("volume_ratio_5d"),
        )

        return {
            "symbol": item.vt_symbol,
            "name": item.name,
            "scope": scope or "daily",
            "horizon_days": horizon_days,
            "as_of": technical.get("as_of") or momentum.get("as_of"),
            "technical": {
                "last_close": technical.get("last_close"),
                "ma": technical.get("ma"),
                "ma_alignment": technical.get("ma_alignment"),
                "volume_ratio_5d": technical.get("volume_ratio_5d"),
                "period_return": technical.get("period_return"),
            },
            "momentum": {
                "lookback_days": momentum.get("lookback_days"),
                "return_pct": momentum.get("return_pct"),
                "volatility_pct": momentum.get("volatility_pct"),
                "range_pct": momentum.get("range_pct"),
                "trend_label": momentum.get("trend_label"),
                "pattern_label": momentum.get("pattern_label"),
            },
            "structure_anchors": structure,
            "reference_bands": reference_bands,
            "direction_hints": direction_hints,
            "output_guide": (
                "请基于上述本地数据直接输出 bull/base/bear 三情景（概率表述 + 触发/失效条件）；通常无需再调用其他工具；禁止确定性预测与具体买卖价位。"
            ),
            "supplement_tools": [],
            "warnings": list(dict.fromkeys(warnings)),
            "sources": ["bar"],
            "disclaimer": "以上为本地规则与统计参考，情景分析不构成投资建议或确定性预测。",
        }

    def _estimate_daily_volatility_pct(
        self,
        symbol: str,
        *,
        scope: str = "daily",
        window: int = 20,
    ) -> float | None:
        item = parse_stock_symbol(symbol)
        if item is None:
            return None
        bars = self._engine.bar_service.load_bars(item.symbol, item.exchange, scope or "daily")
        if len(bars) < 3:
            return None
        tail = bars[-max(5, min(int(window or 20), 60)) :]
        closes = [bar.close_price for bar in tail]
        daily_changes: list[float] = []
        for index in range(1, len(closes)):
            prev = closes[index - 1]
            if prev:
                daily_changes.append((closes[index] - prev) / prev * 100)
        if len(daily_changes) < 2:
            return None
        mean_change = sum(daily_changes) / len(daily_changes)
        variance = sum((value - mean_change) ** 2 for value in daily_changes) / len(daily_changes)
        return round(variance**0.5, 2)

    @staticmethod
    def _build_direction_hints(
        *,
        ma_alignment: str,
        structure: dict[str, Any],
        momentum_return_pct: float | None,
        volume_ratio: float | None,
    ) -> list[str]:
        hints: list[str] = []
        if "多头" in ma_alignment:
            hints.append("均线结构偏多")
        elif "空头" in ma_alignment:
            hints.append("均线结构偏空")
        elif ma_alignment:
            hints.append("均线交织，方向待确认")

        signal = str(structure.get("signal") or "na")
        signal_label = str(structure.get("signal_label") or "")
        if signal == "buy":
            hints.append(f"规则信号偏多：{signal_label or '买入'}（非买卖建议）")
        elif signal == "sell":
            hints.append(f"规则信号偏空：{signal_label or '卖出'}（非买卖建议）")
        elif signal == "hold":
            hints.append(f"规则信号观望：{signal_label or '持有'}")

        if momentum_return_pct is not None:
            if momentum_return_pct >= 3:
                hints.append(f"近段动能偏强（区间涨跌 {momentum_return_pct:+.2f}%）")
            elif momentum_return_pct <= -3:
                hints.append(f"近段动能偏弱（区间涨跌 {momentum_return_pct:+.2f}%）")

        if volume_ratio is not None:
            if volume_ratio >= 1.3:
                hints.append(f"近期量比放大（{volume_ratio:.2f}）")
            elif volume_ratio <= 0.7:
                hints.append(f"近期量比萎缩（{volume_ratio:.2f}）")

        ref_buy = structure.get("ref_buy_price")
        ref_sell = structure.get("ref_sell_price")
        if ref_buy is not None and ref_sell is not None:
            hints.append(f"结构锚点：支撑 {ref_buy} / 阻力 {ref_sell}")

        return hints

    def build_screening_context(
        self,
        *,
        run_id: str | None = None,
        batch_top_n: int = 0,
    ) -> dict[str, Any]:
        """读取选股结果；可选历史 run_id 与批量技术面快照。"""
        screening_svc = getattr(self._engine, "screening_service", None)

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

    def build_screening_explanation(
        self,
        *,
        run_id: str | None = None,
        batch_top_n: int = 5,
    ) -> dict[str, Any]:
        """编排选股解读上下文：结果快照 + 板块分布 + 同配方 diff + 可选技术面。"""
        payload = self.build_screening_context(run_id=run_id, batch_top_n=batch_top_n)
        if payload.get("message") and not payload.get("count"):
            return payload

        rows: list[dict[str, Any]] = []
        recipe_id = ""
        if run_id:
            record = get_run(run_id.strip())
            if record is not None:
                rows = list(record.rows)
                recipe_id = str(record.config.get("recipe_id") or "")
                if record.config.get("run_diff"):
                    payload["run_diff"] = dict(record.config["run_diff"])
        else:
            screening_svc = getattr(self._engine, "screening_service", None)
            ctx = screening_svc.get_screening_results() if screening_svc is not None else get_screening_results()
            if ctx is not None:
                rows = list(ctx.rows)

        if rows:
            enriched = attach_industry(rows)
            payload["sector_distribution"] = compute_sector_distribution(enriched)
            preview = payload.get("preview") or []
            industry_by_vt = {str(r.get("vt_symbol") or ""): str(r.get("industry") or "") for r in enriched}
            for item in preview:
                if isinstance(item, dict):
                    vt = str(item.get("vt_symbol") or "")
                    if vt in industry_by_vt and industry_by_vt[vt]:
                        item["industry"] = industry_by_vt[vt]

        if recipe_id and "run_diff" not in payload:
            previous = find_previous_run_by_recipe(recipe_id, exclude_run_id=run_id or "")
            if previous is not None and rows:
                payload["run_diff"] = compute_run_diff(rows, previous.rows)
                payload["run_diff"]["previous_run_id"] = previous.id

        payload["interpretation_hints"] = [
            "先概括板块分布与新增/保留标的，再逐只解读 Top 标的",
            "单票深度分析可继续调用 diagnose_stock",
            "大盘环境可选 get_ashare_fear_greed_index",
            "禁止编造未在结果中的指标或标的",
        ]
        return payload

    def _benchmark_return_pct(self, lookback: int = SIGNAL_BENCHMARK_LOOKBACK) -> float | None:
        if self._benchmark_return_cache_key == lookback:
            return self._benchmark_return_cache_val
        value = resolve_benchmark_return_pct(self._engine.bar_service, lookback=lookback)
        self._benchmark_return_cache_key = lookback
        self._benchmark_return_cache_val = value
        return value

    def _relative_index_excess(
        self,
        symbol: str,
        exchange: Any,
        *,
        lookback: int = SIGNAL_BENCHMARK_LOOKBACK,
    ) -> float | None:
        bench_pct = self._benchmark_return_pct(lookback)
        return compute_relative_index_excess(
            self._engine.bar_service,
            symbol,
            exchange,
            lookback=lookback,
            benchmark_pct=bench_pct,
        )

    def enrich_relative_index(self, snapshot: SignalSnapshot) -> SignalSnapshot:
        """旧快照缺 relative_index_pct 时补算（不改动其它字段）。"""
        if snapshot.relative_index_pct is not None or snapshot.signal == "na":
            return snapshot
        item = parse_stock_symbol(snapshot.vt_symbol)
        if item is None:
            return snapshot
        excess = self._relative_index_excess(item.symbol, item.exchange)
        if excess is None:
            return snapshot
        from dataclasses import replace

        return replace(snapshot, relative_index_pct=excess)

    def enrich_relative_index_batch(
        self,
        snapshots: dict[str, SignalSnapshot],
    ) -> dict[str, SignalSnapshot]:
        if not snapshots:
            return snapshots
        self.reset_benchmark_cache()
        enriched: dict[str, SignalSnapshot] = {}
        for vt_symbol, snapshot in snapshots.items():
            enriched[vt_symbol] = self.enrich_relative_index(snapshot)
        return enriched

    def _build_signal_payload(
        self,
        symbol: str,
        *,
        class_name: str,
        lookback: int,
        fast_window: int,
        slow_window: int,
        scope: str,
    ) -> dict[str, Any] | None:
        item = parse_stock_symbol(symbol)
        if item is None:
            return None
        if class_name not in SUPPORTED_SIGNAL_STRATEGIES:
            return None

        lookback = max(30, min(int(lookback or 120), 250))
        fast_window = max(2, int(fast_window or 10))
        slow_window = max(fast_window + 1, int(slow_window or 20))

        bars = self._engine.bar_service.load_bars(
            item.symbol,
            item.exchange,
            scope or "daily",
        )
        if len(bars) < slow_window + 5:
            return {
                "vt_symbol": item.vt_symbol,
                "strategy_id": class_name,
                "as_of": "",
                "signal": "na",
                "signal_label": "—",
                "signal_date": None,
                "ref_buy_price": None,
                "ref_sell_price": None,
                "action_ref_buy_price": None,
                "action_ref_sell_price": None,
                "strength": None,
                "reason_summary": "",
                "reasons": (),
                "warnings": ("本地 K 线不足，请先在数据管理页下载日 K",),
            }

        tail = bars[-lookback:] if len(bars) >= lookback else bars
        closes = [bar.close_price for bar in tail]
        highs = [bar.high_price for bar in tail]
        lows = [bar.low_price for bar in tail]
        volumes = [float(bar.volume) for bar in tail]
        dates = [bar.datetime for bar in tail]

        if SUPPORTED_SIGNAL_STRATEGIES.get(class_name) is None:
            return None

        relative_index_pct = self._relative_index_excess(
            item.symbol,
            item.exchange,
        )
        payload = build_signal_payload_for_strategy(
            class_name,
            closes,
            dates,
            vt_symbol=item.vt_symbol,
            fast_window=fast_window,
            slow_window=slow_window,
            highs=highs,
            lows=lows,
            volumes=volumes,
            relative_index_pct=relative_index_pct,
        )
        if payload is None:
            return None
        payload["relative_index_pct"] = relative_index_pct
        return payload

    @staticmethod
    def _payload_to_signal_snapshot(payload: dict[str, Any]) -> SignalSnapshot:
        return SignalSnapshot(
            vt_symbol=str(payload.get("vt_symbol") or ""),
            strategy_id=str(payload.get("strategy_id") or ""),
            as_of=str(payload.get("as_of") or ""),
            signal=payload.get("signal") or "na",
            signal_label=str(payload.get("signal_label") or "—"),
            signal_date=payload.get("signal_date"),
            ref_buy_price=payload.get("ref_buy_price"),
            ref_sell_price=payload.get("ref_sell_price"),
            strength=payload.get("strength"),
            reason_summary=str(payload.get("reason_summary") or ""),
            reasons=tuple(payload.get("reasons") or ()),
            warnings=tuple(payload.get("warnings") or ()),
            last_close=payload.get("last_close"),
            action_ref_buy_price=payload.get("action_ref_buy_price"),
            action_ref_sell_price=payload.get("action_ref_sell_price"),
            fast_ma=payload.get("fast_ma"),
            slow_ma=payload.get("slow_ma"),
            volume_ratio_5d=payload.get("volume_ratio_5d"),
            ma_gap_pct=payload.get("ma_gap_pct"),
            strength_cross=payload.get("strength_cross"),
            strength_alignment=payload.get("strength_alignment"),
            strength_volume=payload.get("strength_volume"),
            strength_pattern=payload.get("strength_pattern"),
            relative_index_pct=payload.get("relative_index_pct"),
        )

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
