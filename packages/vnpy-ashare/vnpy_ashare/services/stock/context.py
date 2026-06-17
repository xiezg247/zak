"""个股分析弹窗：指标抽取、质量提示与资金流摘要。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import MutableModel

from datetime import timedelta
from typing import Any

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.domain.time.china import china_now, format_china_date_compact
from vnpy_ashare.domain.trading.signal_benchmark import resolve_benchmark_return_pct
from vnpy_ashare.domain.trading.signal_snapshot import SIGNAL_LABELS, SignalSnapshot
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.screener.data.data_source import fetch_moneyflow_with_fallback
from vnpy_ashare.storage.repositories.financial import FinancialSnapshotRow


class DiagnoseMetrics(MutableModel):
    macd: float | None = Field(default=None, description="MACD 值")
    dif: float | None = Field(default=None, description="DIF 值")
    dea: float | None = Field(default=None, description="DEA 值")
    kdj_k: float | None = Field(default=None, description="kdj k")
    kdj_d: float | None = Field(default=None, description="kdj d")
    kdj_j: float | None = Field(default=None, description="kdj j")
    rsi: float | None = Field(default=None, description="RSI 值")
    pe_ttm: float | None = Field(default=None, description="市盈率 TTM")
    roe: float | None = Field(default=None, description="净资产收益率")
    main_net: float | None = Field(default=None, description="主力净流入")
    industry: str = Field(default="", description="所属行业")
    source: str = Field(default="tdx_mcp", description="数据来源")


class MoneyflowDayRow(MutableModel):
    trade_date: str = Field(description="交易日")
    net_mf_amount: float | None = Field(default=None, description="net mf amount")
    buy_elg_amount: float | None = Field(default=None, description="buy elg amount")
    sell_elg_amount: float | None = Field(default=None, description="sell elg amount")


class MoneyflowProfile(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    latest: MoneyflowDayRow | None = Field(default=None, description="latest")
    history: list[MoneyflowDayRow] = Field(default_factory=list, description="history")
    message: str = Field(default="", description="说明信息")


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


def _scan_fields(fields: dict[str, Any]) -> dict[str, float | None]:
    macd = dif = dea = kdj_k = kdj_d = kdj_j = rsi = pe = roe = main_net = None
    for key, raw in fields.items():
        value = _to_float(raw)
        if value is None:
            continue
        upper = key.upper()
        if "MACD.MACD" in key or (upper == "MACD" and macd is None):
            macd = value
        elif "MACD.DIF" in key or "DIF" in upper:
            dif = value
        elif "MACD.DEA" in key or "DEA" in upper:
            dea = value
        elif "KDJ.K" in key or key.endswith(".K") or key == "kdj_k":
            kdj_k = value
        elif "KDJ.D" in key or (".D" in key and "KDJ" in upper) or key == "kdj_d":
            kdj_d = value
        elif "KDJ.J" in key or (".J" in key and "KDJ" in upper) or key == "kdj_j":
            kdj_j = value
        elif "RSI" in upper or key == "rsi":
            rsi = value
        elif "市盈" in key or upper.startswith("PE"):
            pe = value
        elif "ROE" in upper or "净资产收益率" in key:
            roe = value
        elif "主力" in key or key == "main_net":
            main_net = value
    return {
        "macd": macd,
        "dif": dif,
        "dea": dea,
        "kdj_k": kdj_k,
        "kdj_d": kdj_d,
        "kdj_j": kdj_j,
        "rsi": rsi,
        "pe_ttm": pe,
        "roe": roe,
        "main_net": main_net,
    }


def extract_diagnose_metrics(diagnose: dict[str, Any]) -> DiagnoseMetrics:
    """从问小达 diagnose JSON 抽取展示用指标。"""
    if not diagnose or diagnose.get("error"):
        return DiagnoseMetrics()

    technical = diagnose.get("technical") or {}
    fundamental = diagnose.get("fundamental") or {}
    capital_flow = diagnose.get("capital_flow") or {}
    quote = diagnose.get("quote") or {}

    tech_fields = dict(technical.get("fields") or {})
    for key in ("macd", "dif", "dea", "kdj_k", "kdj_d", "kdj_j", "rsi"):
        if technical.get(key) is not None:
            tech_fields.setdefault(key, technical[key])

    fund_fields = dict(fundamental.get("fields") or {})
    if fundamental.get("pe_ttm") is not None:
        fund_fields.setdefault("pe_ttm", fundamental["pe_ttm"])
    if fundamental.get("roe") is not None:
        fund_fields.setdefault("roe", fundamental["roe"])

    flow_fields = dict(capital_flow.get("fields") or {})
    if capital_flow.get("main_net") is not None:
        flow_fields.setdefault("main_net", capital_flow["main_net"])

    merged = _scan_fields({**tech_fields, **fund_fields, **flow_fields})
    return DiagnoseMetrics(
        **merged,
        industry=str(quote.get("industry") or "").strip("@"),
        source=str((diagnose.get("sources") or ["tdx_mcp"])[0]),
    )


def format_technical_summary(
    technical: dict[str, Any],
    *,
    relative_returns: dict[str, float | None] | None = None,
) -> str:
    """本地技术面 + 相对强弱文本摘要。"""
    if not technical:
        base = "暂无本地技术面"
    elif technical.get("error"):
        base = str(technical["error"])
    elif technical.get("warnings"):
        base = "；".join(str(item) for item in technical["warnings"])
    else:
        ma = technical.get("ma") or {}
        period = technical.get("period_return") or {}
        ret = period.get("return_pct")
        ret_text = f"{ret:+.2f}%" if isinstance(ret, (int, float)) else "—"
        lines = [
            f"截至 {technical.get('as_of', '—')} · 收盘 {technical.get('last_close', '—')}",
            "MA5 / MA10 / MA20 / MA60",
            f"{ma.get('ma5', '—')} / {ma.get('ma10', '—')} / {ma.get('ma20', '—')} / {ma.get('ma60', '—')}",
            f"均线排列：{technical.get('ma_alignment', '—')}",
            f"5日量比 {technical.get('volume_ratio_5d', '—')} · 区间涨跌 {ret_text}",
        ]
        rel = relative_returns or {}
        rel_parts: list[str] = []
        for label, key in (("5日", "ret_5d"), ("20日", "ret_20d"), ("60日", "ret_60d")):
            value = rel.get(key)
            if isinstance(value, (int, float)):
                rel_parts.append(f"{label} {value:+.2f}%")
        rs = rel.get("rs_20d")
        if isinstance(rs, (int, float)):
            rel_parts.append(f"相对沪深300(20日) {rs:+.2f}%")
        if rel_parts:
            lines.append(" · ".join(rel_parts))
        return "\n".join(lines)

    return base


def build_financial_quality_hints(snapshots: list[FinancialSnapshotRow]) -> list[str]:
    """基于最新财报快照生成质量提示。"""
    if not snapshots:
        return []
    latest = snapshots[0]
    hints: list[str] = []

    ocf_ratio = latest.ocf_to_profit
    if ocf_ratio is not None:
        if ocf_ratio < 0.5:
            hints.append(f"经营现金流/净利润 {ocf_ratio:.0%}，盈利现金含量偏低")
        elif ocf_ratio >= 1.0:
            hints.append(f"经营现金流/净利润 {ocf_ratio:.0%}，盈利现金含量较好")

    if latest.debt_ratio is not None and latest.debt_ratio > 70:
        hints.append(f"资产负债率 {latest.debt_ratio:.1f}%，杠杆偏高")
    if latest.gross_margin is not None and latest.gross_margin < 15:
        hints.append(f"毛利率 {latest.gross_margin:.1f}%，盈利能力偏弱")

    if latest.revenue_yoy is not None and latest.revenue_yoy < -10:
        hints.append(f"营收同比 {latest.revenue_yoy:+.1f}%，增长承压")
    if latest.net_income_yoy is not None and latest.net_income_yoy < -20:
        hints.append(f"归母净利同比 {latest.net_income_yoy:+.1f}%，业绩下滑明显")

    return hints[:4]


def _row_from_dict(row: dict[str, Any]) -> MoneyflowDayRow:
    return MoneyflowDayRow(
        trade_date=str(row.get("trade_date") or ""),
        net_mf_amount=_to_float(row.get("net_mf_amount")),
        buy_elg_amount=_to_float(row.get("buy_elg_amount")),
        sell_elg_amount=_to_float(row.get("sell_elg_amount")),
    )


def lookup_latest_moneyflow(vt_symbol: str) -> MoneyflowDayRow | None:
    """从 Tushare 全市场 moneyflow 缓存查找单票最新一日。"""
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return None
    try:
        rows, _ = fetch_moneyflow_with_fallback(max_lookback=5)
    except TushareNotConfiguredError:
        return None
    except Exception:
        return None
    for row in rows:
        if row.get("ts_code") == item.ts_code or row.get("vt_symbol") == item.vt_symbol:
            return _row_from_dict(row)
    return None


def fetch_stock_moneyflow_series(ts_code: str, *, days: int = 20) -> list[MoneyflowDayRow]:
    """拉取单票近 N 日主力资金流（万元）。"""
    days = max(5, min(int(days or 20), 60))
    now = china_now()
    end = format_china_date_compact(now)
    start = format_china_date_compact(now - timedelta(days=days * 2))
    try:
        pro = get_tushare_pro()
        frame = pro.moneyflow(
            ts_code=ts_code,
            start_date=start,
            end_date=end,
            fields="ts_code,trade_date,net_mf_amount,buy_elg_amount,sell_elg_amount",
        )
    except TushareNotConfiguredError:
        return []
    except Exception:
        return []
    if frame is None or frame.empty:
        return []

    rows: list[MoneyflowDayRow] = []
    for record in frame.to_dict(orient="records"):
        rows.append(_row_from_dict(record))
    rows.sort(key=lambda item: item.trade_date, reverse=True)
    return rows[:days]


def build_moneyflow_profile(vt_symbol: str, *, history_days: int = 15) -> MoneyflowProfile:
    """组装单票资金流摘要（最新 + 历史序列）。"""
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return MoneyflowProfile(ts_code="", vt_symbol=vt_symbol, message="无法解析代码")

    latest = lookup_latest_moneyflow(vt_symbol)
    history = fetch_stock_moneyflow_series(item.ts_code, days=history_days)
    if not history and latest is not None:
        history = [latest]

    message = ""
    if not history and latest is None:
        message = "暂无资金流数据（需 TUSHARE_TOKEN，并在定时任务启用「主力资金预拉」）"

    return MoneyflowProfile(
        ts_code=item.ts_code,
        vt_symbol=item.vt_symbol,
        latest=latest or (history[0] if history else None),
        history=history,
        message=message,
    )


def signal_summary_label(signal: SignalSnapshot | None) -> str:
    if signal is None or signal.signal == "na":
        return SIGNAL_LABELS["na"]
    return signal.signal_label


def build_analysis_ai_context(payload: Any) -> str:
    """将 StockAnalysisPayload 摘要注入 AI prompt。"""
    parts: list[str] = []
    technical = getattr(payload, "technical", None) or {}
    if technical.get("ma_alignment"):
        parts.append(f"均线 {technical['ma_alignment']}")

    valuation = getattr(payload, "valuation", None)
    if valuation is not None:
        if valuation.pe_percentile_3y is not None:
            parts.append(f"PE 3年分位 {valuation.pe_percentile_3y:.1f}%")
        if valuation.pb_percentile_3y is not None:
            parts.append(f"PB 3年分位 {valuation.pb_percentile_3y:.1f}%")

    bundle = getattr(payload, "financial_bundle", None)
    if bundle is not None and bundle.snapshots:
        snap = bundle.snapshots[0]
        if snap.revenue_yoy is not None:
            parts.append(f"营收同比 {snap.revenue_yoy:+.1f}%")
        if snap.net_income_yoy is not None:
            parts.append(f"净利同比 {snap.net_income_yoy:+.1f}%")

    rel = getattr(payload, "relative_returns", None) or {}
    if rel.get("rs_20d") is not None:
        parts.append(f"20日相对强弱 {rel['rs_20d']:+.2f}%")

    concept = getattr(payload, "concept", None)
    if concept is not None and concept.concepts:
        names = [str(row.get("concept_name") or "") for row in concept.concepts[:5]]
        names = [name for name in names if name]
        if names:
            parts.append(f"概念：{'、'.join(names)}")

    events = getattr(payload, "events", None)
    if events is not None and events.upcoming_hints:
        parts.append(f"近期事件：{'；'.join(events.upcoming_hints[:3])}")

    holders = getattr(payload, "holders", None)
    if holders is not None and holders.holders:
        top = holders.holders[0]
        name = str(top.get("holder_name") or "")
        ratio = top.get("hold_ratio")
        if name and isinstance(ratio, (int, float)):
            parts.append(f"第一大股东 {name} {ratio:.2f}%")

    return "；".join(parts)


def compute_relative_returns(engine: Any, vt_symbol: str) -> dict[str, float | None]:
    """计算多周期涨跌幅与相对沪深300超额。"""
    item = parse_stock_symbol(vt_symbol)
    if item is None or engine is None:
        return {}
    bar_service = getattr(engine, "bar_service", None)
    if bar_service is None:
        return {}

    result: dict[str, float | None] = {}
    for days, key in ((5, "ret_5d"), (20, "ret_20d"), (60, "ret_60d")):
        payload = bar_service.get_return(item.symbol, item.exchange, "daily", lookback_days=days)
        pct = payload.get("return_pct") if isinstance(payload, dict) else None
        result[key] = float(pct) if isinstance(pct, (int, float)) else None

    bench = resolve_benchmark_return_pct(bar_service, lookback=20)
    ret_20 = result.get("ret_20d")
    if ret_20 is not None and bench is not None:
        result["rs_20d"] = round(ret_20 - bench, 2)
    return result
