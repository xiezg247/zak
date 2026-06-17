"""走势情景摘要（技术面 + 结构锚点 + 统计参考带）。"""

from __future__ import annotations

from typing import Any

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.services.analysis_detail.technical.base import _TechnicalAnalyzerBase


class TechnicalScenarioMixin(_TechnicalAnalyzerBase):
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
        return float(round(variance**0.5, 2))

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
