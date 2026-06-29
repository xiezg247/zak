"""个股分析概览仪表盘：数据就绪、关键提醒与选股上下文。"""

from __future__ import annotations

from typing import Any

from vnpy.trader.object import BarData

from vnpy_ashare.ai.context.store import get_screening_results
from vnpy_ashare.ai.context.symbol import parse_stock_symbol
from vnpy_ashare.domain.stock.context import MoneyflowProfile
from vnpy_ashare.domain.stock.overview import (
    AlertSeverity,
    DataReadinessItem,
    OverviewAlert,
    OverviewDashboard,
    ScreeningHit,
)
from vnpy_ashare.domain.stock.profile import ValuationProfile
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.integrations.tushare.stk_shock import load_recent_exchange_regulatory_for_vt_symbol
from vnpy_ashare.quotes.core.limit_times_cache import get_cached_limit_times_map
from vnpy_ashare.services.stock.context import (
    MoneyflowDayRow,
    build_financial_quality_hints,
    build_moneyflow_profile,
)
from vnpy_ashare.services.stock.events import build_disclosure_upcoming_hints
from vnpy_ashare.services.stock.profile import build_valuation_profile
from vnpy_ashare.services.stock.regulatory_deviation import assess_regulatory_deviation_for_vt_symbol
from vnpy_ashare.storage.repositories.valuation import list_valuation_history


def _board_label(boards: int) -> str:
    if boards <= 0:
        return "—"
    return f"{boards}板" if boards > 1 else "首板"


def find_screening_hit(vt_symbol: str) -> ScreeningHit | None:
    ctx = get_screening_results()
    if ctx is None or not ctx.rows:
        return None
    for index, row in enumerate(ctx.rows):
        row_symbol = str(row.get("vt_symbol") or "")
        if row_symbol == vt_symbol:
            return ScreeningHit(
                condition=str(ctx.condition or "选股方案"),
                rank=index + 1,
                total=int(ctx.count or len(ctx.rows)),
                updated_at=ctx.updated_at,
            )
    return None


def _tushare_configured() -> bool:
    try:
        get_tushare_pro()
        return True
    except TushareNotConfiguredError:
        return False


def _readiness_daily_bars(technical: dict[str, Any]) -> DataReadinessItem:
    warnings = [str(item) for item in (technical.get("warnings") or [])]
    last_close = technical.get("last_close")
    bars_used = int(technical.get("bars_used") or 0)
    if any("K 线" in item for item in warnings) or last_close is None:
        return DataReadinessItem(key="daily_bars", label="日K", status="missing", detail="请先下载日K", jump_target="chart")
    as_of = str(technical.get("as_of") or "—")
    if bars_used >= 60:
        return DataReadinessItem(key="daily_bars", label="日K", status="ready", detail=f"截至 {as_of}", jump_target="chart")
    return DataReadinessItem(key="daily_bars", label="日K", status="partial", detail=f"仅 {bars_used} 根 · {as_of}", jump_target="chart")


def _readiness_financial(engine: Any, vt_symbol: str) -> DataReadinessItem:
    financial = getattr(engine, "financial_service", None)
    if financial is None:
        return DataReadinessItem(key="financial", label="财报", status="missing", detail="服务不可用", jump_target="financial")
    bundle = financial.get_bundle(vt_symbol)
    if bundle.snapshots:
        end_date = bundle.snapshots[0].end_date or "—"
        return DataReadinessItem(key="financial", label="财报", status="ready", detail=f"报告期 {end_date}", jump_target="financial")
    if bundle.sync_meta is not None:
        return DataReadinessItem(key="financial", label="财报", status="partial", detail="本地无快照", jump_target="financial")
    return DataReadinessItem(key="financial", label="财报", status="missing", detail="请同步财报", jump_target="financial")


_READINESS_VALUATION_LIMIT = 120


def _readiness_valuation(ts_code: str) -> DataReadinessItem:
    if not ts_code:
        return DataReadinessItem(key="valuation", label="估值", status="missing", detail="无法解析", jump_target="sector")
    history_days = len(list_valuation_history(ts_code, limit=_READINESS_VALUATION_LIMIT))
    if history_days >= _READINESS_VALUATION_LIMIT:
        return DataReadinessItem(key="valuation", label="估值", status="ready", detail=f"历史 {history_days} 日", jump_target="sector")
    if history_days > 0:
        return DataReadinessItem(key="valuation", label="估值", status="partial", detail=f"样本 {history_days} 日", jump_target="sector")
    return DataReadinessItem(key="valuation", label="估值", status="missing", detail="打开板块 Tab 同步", jump_target="sector")


def _readiness_moneyflow_profile(profile: MoneyflowProfile | None, *, tushare_ok: bool) -> DataReadinessItem:
    if not tushare_ok:
        return DataReadinessItem(key="moneyflow", label="资金流", status="unconfigured", detail="需 TUSHARE_TOKEN", jump_target="capital")
    if profile is None:
        return DataReadinessItem(key="moneyflow", label="资金流", status="missing", detail="暂无缓存", jump_target="capital")
    if profile.history:
        latest = profile.latest.trade_date if profile.latest else profile.history[0].trade_date
        detail = f"最新 {latest or '—'}"
        return DataReadinessItem(key="moneyflow", label="资金流", status="ready", detail=detail, jump_target="capital")
    message = profile.message or "暂无数据"
    if "未配置" in message or "TUSHARE" in message.upper():
        return DataReadinessItem(key="moneyflow", label="资金流", status="unconfigured", detail="需 TUSHARE_TOKEN", jump_target="capital")
    return DataReadinessItem(key="moneyflow", label="资金流", status="missing", detail="暂无缓存", jump_target="capital")


def _readiness_holders() -> DataReadinessItem:
    if not _tushare_configured():
        return DataReadinessItem(key="holders", label="股东", status="unconfigured", detail="需 TUSHARE_TOKEN", jump_target="holders")
    return DataReadinessItem(key="holders", label="股东", status="partial", detail="切换 Tab 加载", jump_target="holders")


def _readiness_short_term(vt_symbol: str) -> DataReadinessItem:
    if not _tushare_configured():
        return DataReadinessItem(
            key="short_term",
            label="短线",
            status="unconfigured",
            detail="需 TUSHARE_TOKEN",
            jump_target="short_term",
        )
    item = parse_stock_symbol(vt_symbol)
    if item is not None:
        limit_map = get_cached_limit_times_map()
        boards = limit_map.get(item.tickflow_symbol, 0)
        if boards >= 1:
            return DataReadinessItem(
                key="short_term",
                label="短线",
                status="ready",
                detail=_board_label(int(boards)),
                jump_target="short_term",
            )
    return DataReadinessItem(
        key="short_term",
        label="短线",
        status="partial",
        detail="切换 Tab 加载",
        jump_target="short_term",
    )


def _disclosure_alerts(ts_code: str) -> list[OverviewAlert]:
    if not ts_code:
        return []
    hints = build_disclosure_upcoming_hints(ts_code)
    return [OverviewAlert(text=hint, severity="warn", jump_target="events") for hint in hints[:2]]


def _valuation_alerts_from_profile(profile: ValuationProfile) -> list[OverviewAlert]:
    alerts: list[OverviewAlert] = []
    pe_pct = profile.pe_percentile_3y
    if pe_pct is not None and pe_pct >= 85:
        alerts.append(
            OverviewAlert(
                text=f"PE(TTM) 处于 3 年高位（分位 {pe_pct:.0f}%）",
                severity="warn",
                jump_target="sector",
            )
        )
    elif pe_pct is not None and pe_pct <= 15:
        alerts.append(
            OverviewAlert(
                text=f"PE(TTM) 处于 3 年低位（分位 {pe_pct:.0f}%）",
                severity="info",
                jump_target="sector",
            )
        )
    pb_pct = profile.pb_percentile_3y
    if pb_pct is not None and pb_pct >= 90 and not alerts:
        alerts.append(
            OverviewAlert(
                text=f"PB 处于 3 年高位（分位 {pb_pct:.0f}%）",
                severity="warn",
                jump_target="sector",
            )
        )
    return alerts[:1]


def _financial_alerts(engine: Any, vt_symbol: str) -> list[OverviewAlert]:
    financial = getattr(engine, "financial_service", None)
    if financial is None:
        return []
    bundle = financial.get_bundle(vt_symbol)
    if not bundle.snapshots:
        return [
            OverviewAlert(
                text="本地暂无财报快照，可在财务 Tab 同步",
                severity="info",
                jump_target="financial",
            )
        ]
    hints = build_financial_quality_hints(bundle.snapshots)
    return [OverviewAlert(text=hint, severity="warn", jump_target="financial") for hint in hints[:2]]


def _moneyflow_streak_alert(history: list[MoneyflowDayRow]) -> OverviewAlert | None:
    if len(history) < 3:
        return None
    direction: float | None = None
    streak = 0
    for row in history:
        amount = row.net_mf_amount
        if amount is None or amount == 0:
            break
        sign = 1.0 if amount > 0 else -1.0
        if direction is None:
            direction = sign
        if sign != direction:
            break
        streak += 1
    if streak < 3 or direction is None:
        return None
    label = "净流入" if direction > 0 else "净流出"
    return OverviewAlert(
        text=f"主力连续 {streak} 日{label}",
        severity="info",
        jump_target="capital",
    )


_OVERVIEW_REGULATORY_LOOKBACK = 5


def _moneyflow_alerts_from_profile(profile: MoneyflowProfile | None) -> list[OverviewAlert]:
    if profile is None:
        return []
    alert = _moneyflow_streak_alert(profile.history)
    return [alert] if alert is not None else []


def _regulatory_alerts(vt_symbol: str, *, daily_bars: list[BarData] | None = None) -> list[OverviewAlert]:
    exchange_records: tuple[Any, ...] = ()
    if _tushare_configured():
        exchange_records = load_recent_exchange_regulatory_for_vt_symbol(
            vt_symbol,
            lookback_trading_days=_OVERVIEW_REGULATORY_LOOKBACK,
        )
    snapshot = assess_regulatory_deviation_for_vt_symbol(
        vt_symbol,
        bars=daily_bars,
        exchange_records=exchange_records,
    )
    if snapshot is None or snapshot.risk_level == "none":
        return []
    severity: AlertSeverity = "warn" if snapshot.risk_level == "high" else "info"
    return [
        OverviewAlert(
            text=f"监管异动：{snapshot.summary}",
            severity=severity,
            jump_target="short_term",
        )
    ]


def _limit_board_alerts(vt_symbol: str) -> list[OverviewAlert]:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return []
    boards = get_cached_limit_times_map().get(item.tickflow_symbol, 0)
    if boards < 1:
        return []
    return [
        OverviewAlert(
            text=f"涨停 {_board_label(int(boards))}，查看短线档案",
            severity="info",
            jump_target="short_term",
        )
    ]


def build_overview_dashboard(
    engine: Any,
    vt_symbol: str,
    *,
    technical: dict[str, Any],
    daily_bars: list[BarData] | None = None,
) -> OverviewDashboard:
    item = parse_stock_symbol(vt_symbol)
    ts_code = item.ts_code if item is not None else ""
    tushare_ok = _tushare_configured()
    moneyflow_profile = build_moneyflow_profile(vt_symbol, history_days=8) if tushare_ok else None
    valuation_profile = build_valuation_profile(vt_symbol, live=False) if tushare_ok else None

    readiness = [
        _readiness_daily_bars(technical),
        _readiness_short_term(vt_symbol),
        _readiness_financial(engine, vt_symbol),
        _readiness_valuation(ts_code),
        _readiness_moneyflow_profile(moneyflow_profile, tushare_ok=tushare_ok),
        _readiness_holders(),
    ]

    alerts: list[OverviewAlert] = []
    alert_builders: list[Any] = [
        lambda: _limit_board_alerts(vt_symbol),
        lambda: _regulatory_alerts(vt_symbol, daily_bars=daily_bars),
        lambda: _disclosure_alerts(ts_code),
        lambda: _financial_alerts(engine, vt_symbol),
    ]
    if valuation_profile is not None:
        alert_builders.append(lambda profile=valuation_profile: _valuation_alerts_from_profile(profile))
    if moneyflow_profile is not None:
        alert_builders.append(lambda profile=moneyflow_profile: _moneyflow_alerts_from_profile(profile))

    for builder in alert_builders:
        for alert in builder():
            if len(alerts) >= 5:
                break
            if alert.text and alert.text not in {item.text for item in alerts}:
                alerts.append(alert)
        if len(alerts) >= 5:
            break

    return OverviewDashboard(
        readiness=readiness,
        alerts=alerts[:5],
        screening=find_screening_hit(vt_symbol),
    )
