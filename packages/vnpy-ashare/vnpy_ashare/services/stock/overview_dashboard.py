"""个股分析概览仪表盘：数据就绪、关键提醒与选股上下文。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from vnpy_ashare.ai.context import get_screening_results, parse_stock_symbol
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.services.stock.context import (
    MoneyflowDayRow,
    build_financial_quality_hints,
    build_moneyflow_profile,
)
from vnpy_ashare.services.stock.events import build_disclosure_upcoming_hints
from vnpy_ashare.services.stock.profile import build_valuation_profile
from vnpy_ashare.storage.repositories.valuation import list_valuation_history

ReadinessStatus = Literal["ready", "partial", "missing", "unconfigured"]
OverviewJumpTarget = Literal["chart", "sector", "capital", "events", "holders", "financial"]
AlertSeverity = Literal["info", "warn"]


@dataclass(frozen=True)
class DataReadinessItem:
    key: str
    label: str
    status: ReadinessStatus
    detail: str = ""
    jump_target: OverviewJumpTarget | None = None


@dataclass(frozen=True)
class OverviewAlert:
    text: str
    severity: AlertSeverity = "info"
    jump_target: OverviewJumpTarget | None = None


@dataclass(frozen=True)
class ScreeningHit:
    condition: str
    rank: int
    total: int
    updated_at: str | None = None


@dataclass
class OverviewDashboard:
    readiness: list[DataReadinessItem] = field(default_factory=list)
    alerts: list[OverviewAlert] = field(default_factory=list)
    screening: ScreeningHit | None = None


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
        return DataReadinessItem(
            "daily_bars",
            "日K",
            "missing",
            "请先下载日K",
            "chart",
        )
    as_of = str(technical.get("as_of") or "—")
    if bars_used >= 60:
        return DataReadinessItem("daily_bars", "日K", "ready", f"截至 {as_of}", "chart")
    return DataReadinessItem(
        "daily_bars",
        "日K",
        "partial",
        f"仅 {bars_used} 根 · {as_of}",
        "chart",
    )


def _readiness_financial(engine: Any, vt_symbol: str) -> DataReadinessItem:
    financial = getattr(engine, "financial_service", None)
    if financial is None:
        return DataReadinessItem("financial", "财报", "missing", "服务不可用", "financial")
    bundle = financial.get_bundle(vt_symbol)
    if bundle.snapshots:
        end_date = bundle.snapshots[0].end_date or "—"
        return DataReadinessItem("financial", "财报", "ready", f"报告期 {end_date}", "financial")
    if bundle.sync_meta is not None:
        return DataReadinessItem("financial", "财报", "partial", "本地无快照", "financial")
    return DataReadinessItem("financial", "财报", "missing", "请同步财报", "financial")


def _readiness_valuation(ts_code: str) -> DataReadinessItem:
    if not ts_code:
        return DataReadinessItem("valuation", "估值", "missing", "无法解析", "sector")
    history_days = len(list_valuation_history(ts_code, limit=750))
    if history_days >= 120:
        return DataReadinessItem("valuation", "估值", "ready", f"历史 {history_days} 日", "sector")
    if history_days > 0:
        return DataReadinessItem("valuation", "估值", "partial", f"样本 {history_days} 日", "sector")
    return DataReadinessItem("valuation", "估值", "missing", "打开板块 Tab 同步", "sector")


def _readiness_moneyflow(vt_symbol: str) -> DataReadinessItem:
    if not _tushare_configured():
        return DataReadinessItem(
            "moneyflow",
            "资金流",
            "unconfigured",
            "需 TUSHARE_TOKEN",
            "capital",
        )
    profile = build_moneyflow_profile(vt_symbol, history_days=5)
    if profile.history:
        latest = profile.latest.trade_date if profile.latest else profile.history[0].trade_date
        return DataReadinessItem(
            "moneyflow",
            "资金流",
            "ready",
            f"最新 {latest or '—'}",
            "capital",
        )
    message = profile.message or "暂无数据"
    if "未配置" in message or "TUSHARE" in message.upper():
        return DataReadinessItem("moneyflow", "资金流", "unconfigured", "需 TUSHARE_TOKEN", "capital")
    return DataReadinessItem("moneyflow", "资金流", "missing", "暂无缓存", "capital")


def _readiness_holders() -> DataReadinessItem:
    if not _tushare_configured():
        return DataReadinessItem(
            "holders",
            "股东",
            "unconfigured",
            "需 TUSHARE_TOKEN",
            "holders",
        )
    return DataReadinessItem("holders", "股东", "partial", "切换 Tab 加载", "holders")


def _disclosure_alerts(ts_code: str) -> list[OverviewAlert]:
    if not ts_code:
        return []
    hints = build_disclosure_upcoming_hints(ts_code)
    return [OverviewAlert(text=hint, severity="warn", jump_target="events") for hint in hints[:2]]


def _valuation_alerts(vt_symbol: str) -> list[OverviewAlert]:
    profile = build_valuation_profile(vt_symbol)
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


def _moneyflow_alerts(vt_symbol: str) -> list[OverviewAlert]:
    if not _tushare_configured():
        return []
    profile = build_moneyflow_profile(vt_symbol, history_days=8)
    alert = _moneyflow_streak_alert(profile.history)
    return [alert] if alert is not None else []


def build_overview_dashboard(
    engine: Any,
    vt_symbol: str,
    *,
    technical: dict[str, Any],
) -> OverviewDashboard:
    item = parse_stock_symbol(vt_symbol)
    ts_code = item.ts_code if item is not None else ""

    readiness = [
        _readiness_daily_bars(technical),
        _readiness_financial(engine, vt_symbol),
        _readiness_valuation(ts_code),
        _readiness_moneyflow(vt_symbol),
        _readiness_holders(),
    ]

    alerts: list[OverviewAlert] = []
    for builder in (
        lambda: _disclosure_alerts(ts_code),
        lambda: _financial_alerts(engine, vt_symbol),
        lambda: _valuation_alerts(vt_symbol),
        lambda: _moneyflow_alerts(vt_symbol),
    ):
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
