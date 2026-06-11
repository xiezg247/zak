"""本地 K 线技术面、策略信号与选股解读编排。"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine

from strategies.registry import get_strategy_meta
from strategies.signals import (
    SUPPORTED_SIGNAL_STRATEGIES,
    build_double_ma_signal_payload,
    list_supported_signal_strategies,
    summarize_double_ma_state,
)
from vnpy_ashare.ai.context import get_screening_results, parse_stock_symbol
from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.data.pattern_bars import pattern_load_max_workers
from vnpy_ashare.domain.signal_snapshot import SignalSnapshot
from vnpy_ashare.screener.run.run_diff import compute_run_diff
from vnpy_ashare.screener.run.run_store import find_previous_run_by_recipe, get_run
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution


class TechnicalAnalyzer:
    def __init__(self, engine: AshareEngine) -> None:
        self._engine = engine

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
                "strength": None,
                "reason_summary": "",
                "reasons": (),
                "warnings": ("本地 K 线不足，请先在数据管理页下载日 K",),
            }

        tail = bars[-lookback:] if len(bars) >= lookback else bars
        closes = [bar.close_price for bar in tail]
        highs = [bar.high_price for bar in tail]
        volumes = [float(bar.volume) for bar in tail]
        dates = [bar.datetime for bar in tail]

        if SUPPORTED_SIGNAL_STRATEGIES[class_name] != "double_ma":
            return None

        return build_double_ma_signal_payload(
            closes,
            dates,
            vt_symbol=item.vt_symbol,
            strategy_id=class_name,
            fast_window=fast_window,
            slow_window=slow_window,
            highs=highs,
            volumes=volumes,
        )

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
