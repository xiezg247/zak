"""投研团队：确定性数据预取与财务面聚合。"""

from __future__ import annotations

import concurrent.futures
from typing import TYPE_CHECKING, Any

from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.screener.data.data_source import fetch_daily_basic_with_fallback
from vnpy_ashare.services.analysis_detail.market_context import build_team_market_context
from vnpy_ashare.services.stock.context import DiagnoseMetrics, extract_diagnose_metrics
from vnpy_ashare.storage.repositories.financial import FinancialSnapshotRow, list_snapshots
from vnpy_common.domain.serialize import dump_python

if TYPE_CHECKING:
    from vnpy_ashare.services.analysis import AnalysisService

DIAGNOSE_PREFETCH_TIMEOUT_SECONDS = 20


def snapshot_row_to_dict(row: FinancialSnapshotRow) -> dict[str, Any]:
    return {
        "end_date": row.end_date,
        "revenue": row.revenue,
        "net_income": row.net_income,
        "basic_eps": row.basic_eps,
        "roe": row.roe,
        "gross_margin": row.gross_margin,
        "net_margin": row.net_margin,
        "debt_ratio": row.debt_ratio,
        "current_ratio": row.current_ratio,
        "revenue_yoy": row.revenue_yoy,
        "net_income_yoy": row.net_income_yoy,
        "roe_yoy": row.roe_yoy,
        "free_cashflow": row.free_cashflow,
    }


def lookup_daily_basic(vt_symbol: str) -> dict[str, Any] | None:
    """从 Tushare daily_basic 缓存查找单票估值。"""
    try:
        rows, trade_date = fetch_daily_basic_with_fallback()
    except Exception:
        return None

    for row in rows:
        if row.get("vt_symbol") == vt_symbol:
            return {
                "trade_date": trade_date,
                "close": row.get("close"),
                "pe": row.get("pe"),
                "pe_ttm": row.get("pe_ttm"),
                "pb": row.get("pb"),
                "ps": row.get("ps"),
                "total_mv": row.get("total_mv"),
                "circ_mv": row.get("circ_mv"),
                "turnover_rate": row.get("turnover_rate"),
                "volume_ratio": row.get("volume_ratio"),
            }
    return None


def build_financial_extras(ts_code: str, vt_symbol: str) -> dict[str, Any]:
    """合并本地财报快照与 daily_basic 估值。"""
    snapshots = list_snapshots(ts_code, limit=4)
    latest = snapshots[0] if snapshots else None
    valuation = lookup_daily_basic(vt_symbol)

    latest_dict = snapshot_row_to_dict(latest) if latest else None
    has_roe = latest_dict is not None and latest_dict.get("roe") is not None
    has_margin = latest_dict is not None and latest_dict.get("gross_margin") is not None
    has_yoy = latest_dict is not None and latest_dict.get("net_income_yoy") is not None
    has_debt = latest_dict is not None and latest_dict.get("debt_ratio") is not None
    has_pe = valuation is not None and valuation.get("pe_ttm") is not None

    return {
        "valuation": valuation,
        "latest_financials": latest_dict,
        "financial_history": [snapshot_row_to_dict(row) for row in snapshots],
        "data_availability": {
            "roe": has_roe,
            "gross_margin": has_margin,
            "net_profit_yoy": has_yoy,
            "revenue_cagr_3y": False,
            "debt_ratio": has_debt,
            "current_ratio": latest_dict is not None and latest_dict.get("current_ratio") is not None,
            "pe_ttm": has_pe,
            "pb": valuation is not None and valuation.get("pb") is not None,
        },
        "note": (
            "估值来自 Tushare daily_basic 缓存；财报指标来自本地 financial_snapshots（需先同步财报）。"
            if snapshots or valuation
            else "暂无本地财报与 daily_basic 缓存，仅提供 K 线覆盖。"
        ),
    }


def _resolve_vt_symbol(symbol: str) -> str | None:
    item = parse_stock_symbol(symbol)
    return item.vt_symbol if item else None


def _metrics_to_dict(metrics: DiagnoseMetrics) -> dict[str, Any]:
    data = dump_python(metrics)
    return {key: value for key, value in data.items() if value is not None and value != ""}


def _resolve_cached_diagnose(service: AnalysisService, vt_symbol: str) -> dict[str, Any] | None:
    cached = service.get_diagnose_result()
    if not cached or cached.get("error"):
        return None
    cached_vt = _resolve_vt_symbol(str(cached.get("symbol") or ""))
    if cached_vt != vt_symbol:
        return None
    return cached


def _fetch_diagnose_mcp(service: AnalysisService, symbol: str) -> dict[str, Any] | None:
    """调用 diagnose_stock 同源 MCP 诊断，并写入 context 缓存。"""
    try:
        result = service.diagnose(symbol)
    except Exception:
        return None
    if result.get("error"):
        return None
    service.set_diagnose_result(result)
    return result


def _enrich_financial_from_diagnose(
    financial: dict[str, Any],
    metrics: DiagnoseMetrics,
    *,
    source_label: str,
) -> None:
    """用问小达诊断补全本地缺失的 PE / ROE。"""
    if financial.get("error"):
        return

    valuation = dict(financial.get("valuation") or {})
    latest = dict(financial.get("latest_financials") or {}) if financial.get("latest_financials") else {}
    availability = dict(financial.get("data_availability") or {})
    enriched = False

    if metrics.pe_ttm is not None and valuation.get("pe_ttm") is None:
        valuation["pe_ttm"] = metrics.pe_ttm
        valuation["source"] = source_label
        availability["pe_ttm"] = True
        enriched = True

    if metrics.roe is not None and latest.get("roe") is None:
        latest["roe"] = metrics.roe
        availability["roe"] = True
        enriched = True

    if valuation:
        financial["valuation"] = valuation
    if latest:
        financial["latest_financials"] = latest
    financial["data_availability"] = availability
    if enriched:
        note = str(financial.get("note") or "").strip()
        suffix = f"部分估值/ROE 来自问小达诊断（{source_label}）"
        financial["note"] = f"{note}；{suffix}".strip("；")


def _enrich_strategy_from_diagnose(
    strategy: dict[str, Any],
    metrics: DiagnoseMetrics,
    *,
    source_label: str,
) -> None:
    """将问小达技术指标并入策略维度参考。"""
    if strategy.get("error"):
        return

    indicators: dict[str, float] = {}
    for key in ("macd", "dif", "dea", "kdj_k", "kdj_d", "kdj_j", "rsi"):
        value = getattr(metrics, key, None)
        if value is not None:
            indicators[key] = value
    if metrics.main_net is not None:
        indicators["main_net"] = metrics.main_net

    if indicators:
        strategy["diagnose_indicators"] = indicators
        strategy["diagnose_source"] = source_label


def attach_diagnose_snapshot(
    payload: dict[str, Any],
    diagnose: dict[str, Any] | None,
    *,
    source: str,
) -> None:
    """并入问小达诊断快照（缓存或 diagnose_stock 并行拉取）。"""
    vt_symbol = payload.get("symbol")
    if not vt_symbol:
        return

    if not diagnose or diagnose.get("error"):
        payload["diagnose"] = {
            "available": False,
            "note": "问小达诊断不可用；可先运行「综合诊断」或检查 MCP 配置",
        }
        return

    diagnose_vt = _resolve_vt_symbol(str(diagnose.get("symbol") or ""))
    if diagnose_vt != vt_symbol:
        payload["diagnose"] = {
            "available": False,
            "note": f"诊断标的为 {diagnose.get('symbol')}，与当前 {vt_symbol} 不一致",
        }
        return

    metrics = extract_diagnose_metrics(diagnose)
    payload["diagnose"] = {
        "available": True,
        "source": source,
        "as_of": diagnose.get("as_of"),
        "metrics": _metrics_to_dict(metrics),
    }
    _enrich_financial_from_diagnose(payload.get("financial") or {}, metrics, source_label=source)
    _enrich_strategy_from_diagnose(payload.get("strategy") or {}, metrics, source_label=source)


def attach_diagnose_cache(service: AnalysisService, payload: dict[str, Any]) -> None:
    """兼容入口：仅读取 context_store 缓存。"""
    vt_symbol = payload.get("symbol")
    if not vt_symbol:
        return
    cached = _resolve_cached_diagnose(service, vt_symbol)
    attach_diagnose_snapshot(payload, cached, source="context_cache")


def attach_ultra_short_strategy_context(service: AnalysisService, payload: dict[str, Any]) -> None:
    """并入极致短线维度：情绪周期 + 打板/突破信号。"""
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict) or strategy.get("error"):
        return
    symbol = str(payload.get("symbol") or strategy.get("symbol") or "")
    if not symbol:
        return

    emotion = None
    try:
        emotion = load_emotion_cycle_snapshot(fetch_if_missing=True)
    except Exception:
        emotion = None

    limit_board: dict[str, Any] = {}
    short_breakout: dict[str, Any] = {}
    try:
        limit_board = service.strategy_signals(
            symbol,
            class_name="AshareLimitBoardStrategy",
            fast_window=5,
            slow_window=10,
        )
        short_breakout = service.strategy_signals(
            symbol,
            class_name="AshareShortBreakoutStrategy",
            fast_window=5,
            slow_window=10,
        )
    except Exception:
        pass

    strategy["ultra_short"] = {
        "emotion_stage": emotion.stage if emotion is not None else "",
        "emotion_stage_label": emotion.stage_label if emotion is not None else "",
        "allow_new_positions": emotion.allow_new_positions if emotion is not None else True,
        "limit_board_signal": str(limit_board.get("signal") or ""),
        "limit_board_label": str(limit_board.get("signal_label") or ""),
        "short_breakout_signal": str(short_breakout.get("signal") or ""),
        "short_breakout_label": str(short_breakout.get("signal_label") or ""),
    }


def prefetch_team_facts(service: AnalysisService, symbol: str) -> dict[str, Any]:
    """并行预取财务 / 风险 / 策略 + 可选问小达诊断（diagnose_stock 同源）。"""
    item = parse_stock_symbol(symbol)
    if item is None:
        return {"symbol": symbol, "error": f"无法解析代码: {symbol}"}

    cached_diagnose = _resolve_cached_diagnose(service, item.vt_symbol)
    diagnose_source = "context_cache"
    diagnose_data = cached_diagnose

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_fin = executor.submit(service.analyze_financial, symbol)
        future_risk = executor.submit(service.analyze_risk, symbol)
        future_str = executor.submit(service.analyze_strategy, symbol)
        future_diag = None
        if diagnose_data is None:
            future_diag = executor.submit(_fetch_diagnose_mcp, service, symbol)
            diagnose_source = "diagnose_stock"

        financial = future_fin.result()
        risk = future_risk.result()
        strategy = future_str.result()

        if future_diag is not None:
            try:
                diagnose_data = future_diag.result(timeout=DIAGNOSE_PREFETCH_TIMEOUT_SECONDS)
            except concurrent.futures.TimeoutError:
                diagnose_data = None

    payload = {
        "symbol": item.vt_symbol,
        "name": item.name,
        "financial": financial,
        "risk": risk,
        "strategy": strategy,
    }
    if diagnose_data is None and cached_diagnose is None and future_diag is not None:
        attach_diagnose_snapshot(payload, None, source=diagnose_source)
    else:
        attach_diagnose_snapshot(payload, diagnose_data, source=diagnose_source)

    payload["market_context"] = build_team_market_context(
        service,
        item,
        diagnose=diagnose_data,
    )
    attach_ultra_short_strategy_context(service, payload)
    return payload
