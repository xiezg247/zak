"""个股财报同步、衍生指标与查询。"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from vnpy_ashare.ai.context import parse_stock_symbol
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError
from vnpy_ashare.integrations.tushare.financial import (
    fetch_all_financial_reports,
    field_float,
    infer_period,
)
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.storage.app_db import load_watchlist_rows
from vnpy_ashare.storage.disclosure_store import latest_ann_date_after
from vnpy_ashare.storage.financial_store import (
    REPORT_TYPES,
    FinancialSnapshotRow,
    FinancialSyncMeta,
    get_sync_meta,
    list_reports,
    list_snapshots,
    touch_access,
    upsert_report,
    upsert_snapshot,
    upsert_sync_meta,
)

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine

_EARNINGS_SEASON_MONTHS = {1, 4, 7, 10}
_DEFAULT_TTL_DAYS = 7
_EARNINGS_TTL_DAYS = 1
_SYNC_DELAY_SECONDS = 0.35


@dataclass
class FinancialSyncResult:
    ts_code: str
    vt_symbol: str
    synced: bool
    skipped: bool = False
    message: str = ""
    periods_written: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass
class FinancialBundle:
    ts_code: str
    vt_symbol: str
    name: str
    sync_meta: FinancialSyncMeta | None
    snapshots: list[FinancialSnapshotRow]
    reports: dict[str, list[dict[str, Any]]]


def _prior_year_end_date(end_date: str) -> str | None:
    text = str(end_date or "").strip()
    if len(text) != 8 or not text.isdigit():
        return None
    year = int(text[:4]) - 1
    return f"{year}{text[4:]}"


def _yoy(current: float | None, previous: float | None) -> float | None:
    if current is None or previous is None or previous == 0:
        return None
    return round((current - previous) / abs(previous) * 100, 2)


def _index_by_end(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    mapping: dict[str, dict[str, Any]] = {}
    for row in rows:
        end_date = str(row.get("end_date") or "")
        if end_date:
            mapping[end_date] = row
    return mapping


def compute_snapshots(ts_code: str) -> list[FinancialSnapshotRow]:
    """由本地 financial_reports 重算衍生快照。"""
    income_rows = _index_by_end(list_reports(ts_code, "income", limit=40))
    balance_rows = _index_by_end(list_reports(ts_code, "balancesheet", limit=40))
    cashflow_rows = _index_by_end(list_reports(ts_code, "cashflow", limit=40))
    indicator_rows = _index_by_end(list_reports(ts_code, "fina_indicator", limit=40))

    end_dates = sorted(
        set(income_rows) | set(balance_rows) | set(cashflow_rows) | set(indicator_rows),
        reverse=True,
    )
    snapshots: list[FinancialSnapshotRow] = []
    for end_date in end_dates:
        income = (income_rows.get(end_date) or {}).get("fields") or {}
        balance = (balance_rows.get(end_date) or {}).get("fields") or {}
        cashflow = (cashflow_rows.get(end_date) or {}).get("fields") or {}
        indicator = (indicator_rows.get(end_date) or {}).get("fields") or {}

        revenue = field_float(income, "total_revenue", "revenue")
        net_income = field_float(income, "n_income_attr_p", "n_income")
        operate_profit = field_float(income, "operate_profit")
        basic_eps = field_float(income, "basic_eps", "eps")

        total_assets = field_float(balance, "total_assets")
        total_liab = field_float(balance, "total_liab")
        total_equity = field_float(balance, "total_hldr_eqy_exc_min_int", "total_hldr_eqy")

        ocf = field_float(cashflow, "n_cashflow_act")
        icf = field_float(cashflow, "n_cashflow_inv_act")
        fcf_flow = field_float(cashflow, "n_cash_flows_fnc_act")
        capex = field_float(cashflow, "c_pay_acq_const_fiolta")
        free_cashflow = None
        if ocf is not None and capex is not None:
            free_cashflow = round(ocf - capex, 2)

        roe = field_float(indicator, "roe")
        gross_margin = field_float(indicator, "grossprofit_margin", "gross_margin")
        net_margin = field_float(indicator, "netprofit_margin", "net_margin")
        debt_ratio = field_float(indicator, "debt_to_assets")
        current_ratio = field_float(indicator, "current_ratio")

        prior_end = _prior_year_end_date(end_date)
        prior_income = (income_rows.get(prior_end or "") or {}).get("fields") or {}
        prior_indicator = (indicator_rows.get(prior_end or "") or {}).get("fields") or {}
        prior_revenue = field_float(prior_income, "total_revenue", "revenue")
        prior_net_income = field_float(prior_income, "n_income_attr_p", "n_income")
        prior_roe = field_float(prior_indicator, "roe")

        ocf_to_profit = None
        if ocf is not None and net_income not in (None, 0):
            ocf_to_profit = round(ocf / net_income, 2)

        snapshot = FinancialSnapshotRow(
            ts_code=ts_code,
            end_date=end_date,
            revenue=revenue,
            net_income=net_income,
            operate_profit=operate_profit,
            basic_eps=basic_eps,
            total_assets=total_assets,
            total_liab=total_liab,
            total_equity=total_equity,
            ocf=ocf,
            icf=icf,
            fcf_flow=fcf_flow,
            free_cashflow=free_cashflow,
            roe=roe,
            gross_margin=gross_margin,
            net_margin=net_margin,
            debt_ratio=debt_ratio,
            current_ratio=current_ratio,
            revenue_yoy=_yoy(revenue, prior_revenue),
            net_income_yoy=_yoy(net_income, prior_net_income),
            roe_yoy=_yoy(roe, prior_roe),
            ocf_to_profit=ocf_to_profit,
            computed_at=datetime.now().isoformat(timespec="seconds"),
        )
        upsert_snapshot(snapshot)
        snapshots.append(snapshot)
    return snapshots


def _needs_sync(meta: FinancialSyncMeta | None, *, force: bool, ts_code: str = "") -> bool:
    if force or meta is None:
        return True
    if not meta.last_sync_at:
        return True
    try:
        last_sync = datetime.fromisoformat(meta.last_sync_at)
    except ValueError:
        return True
    if ts_code:
        last_day = last_sync.strftime("%Y%m%d")
        if latest_ann_date_after(ts_code, last_day):
            return True
    ttl_days = _EARNINGS_TTL_DAYS if datetime.now().month in _EARNINGS_SEASON_MONTHS else _DEFAULT_TTL_DAYS
    return datetime.now() - last_sync > timedelta(days=ttl_days)


def sync_symbol_financials(
    vt_symbol: str,
    *,
    years: int = 5,
    force: bool = False,
    delay: float = _SYNC_DELAY_SECONDS,
) -> FinancialSyncResult:
    """增量同步单票三表到本地。"""
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return FinancialSyncResult(
            ts_code="",
            vt_symbol=vt_symbol,
            synced=False,
            message=f"无法解析代码: {vt_symbol}",
        )

    ts_code = item.ts_code
    meta = get_sync_meta(ts_code)
    if not _needs_sync(meta, force=force, ts_code=ts_code):
        touch_access(ts_code)
        return FinancialSyncResult(
            ts_code=ts_code,
            vt_symbol=item.vt_symbol,
            synced=False,
            skipped=True,
            message="本地财报仍有效，跳过同步",
            periods_written=meta.periods_count if meta else 0,
        )

    try:
        fetched = fetch_all_financial_reports(ts_code, years=years)
    except TushareNotConfiguredError as ex:
        return FinancialSyncResult(
            ts_code=ts_code,
            vt_symbol=item.vt_symbol,
            synced=False,
            message=str(ex),
        )
    except Exception as ex:
        upsert_sync_meta(
            FinancialSyncMeta(
                ts_code=ts_code,
                last_sync_at=datetime.now().isoformat(timespec="seconds"),
                sync_status="error",
                error_message=str(ex),
                last_access_at=datetime.now().isoformat(timespec="seconds"),
            )
        )
        return FinancialSyncResult(
            ts_code=ts_code,
            vt_symbol=item.vt_symbol,
            synced=False,
            message=str(ex),
        )

    warnings: list[str] = []
    written = 0
    latest_end = ""
    latest_ann = ""
    now = datetime.now().isoformat(timespec="seconds")

    for report_type in REPORT_TYPES:
        rows = fetched.get(report_type) or []
        if not rows:
            warnings.append(f"{report_type} 无数据")
        for row in rows:
            end_date = str(row.get("end_date") or "")
            ann_date = str(row.get("ann_date") or "")
            period = str(row.get("period") or infer_period(end_date))
            fields = row.get("fields") or {}
            upsert_report(
                ts_code=ts_code,
                report_type=report_type,
                end_date=end_date,
                ann_date=ann_date,
                period=period,
                payload=fields,
            )
            written += 1
            if end_date > latest_end:
                latest_end = end_date
            if ann_date > latest_ann:
                latest_ann = ann_date
        if delay > 0 and report_type != REPORT_TYPES[-1]:
            time.sleep(delay)

    snapshots = compute_snapshots(ts_code)
    upsert_sync_meta(
        FinancialSyncMeta(
            ts_code=ts_code,
            last_sync_at=now,
            latest_end_date=latest_end,
            latest_ann_date=latest_ann,
            sync_status="ok" if snapshots else "partial",
            error_message="",
            periods_count=len(snapshots),
            last_access_at=now,
        )
    )
    return FinancialSyncResult(
        ts_code=ts_code,
        vt_symbol=item.vt_symbol,
        synced=True,
        message=f"已同步 {written} 条财报记录，衍生 {len(snapshots)} 期快照",
        periods_written=len(snapshots),
        warnings=warnings,
    )


def sync_watchlist_financials(
    *,
    years: int = 5,
    force: bool = False,
    delay: float = _SYNC_DELAY_SECONDS,
) -> tuple[int, int, list[str]]:
    """同步自选池全部标的财报。返回 (成功数, 跳过数, 消息列表)。"""
    rows = load_watchlist_rows()
    if not rows:
        return 0, 0, ["自选池为空"]

    ok = 0
    skipped = 0
    messages: list[str] = []
    for symbol, exchange, _name in rows:
        vt_symbol = f"{symbol}.{exchange.value}"
        result = sync_symbol_financials(vt_symbol, years=years, force=force, delay=delay)
        if result.skipped:
            skipped += 1
        elif result.synced:
            ok += 1
            messages.append(f"{vt_symbol}: {result.message}")
        else:
            messages.append(f"{vt_symbol}: {result.message}")
    summary = f"自选财报同步完成：成功 {ok}，跳过 {skipped}，共 {len(rows)} 只"
    return ok, skipped, [summary, *messages[:8]]


def load_financial_bundle(vt_symbol: str, *, periods: int = 12) -> FinancialBundle | None:
    item = parse_stock_symbol(vt_symbol)
    if item is None:
        return None
    ts_code = item.ts_code
    touch_access(ts_code)
    reports = {report_type: list_reports(ts_code, report_type, limit=periods) for report_type in REPORT_TYPES}
    return FinancialBundle(
        ts_code=ts_code,
        vt_symbol=item.vt_symbol,
        name=item.name,
        sync_meta=get_sync_meta(ts_code),
        snapshots=list_snapshots(ts_code, limit=periods),
        reports=reports,
    )


class FinancialService(BaseService):
    """个股财报 Service（同步、查询）。"""

    def __init__(self, engine: AshareEngine) -> None:
        super().__init__(engine)

    def sync(self, vt_symbol: str, *, years: int = 5, force: bool = False) -> FinancialSyncResult:
        return sync_symbol_financials(vt_symbol, years=years, force=force)

    def get_bundle(self, vt_symbol: str, *, periods: int = 12) -> FinancialBundle | None:
        return load_financial_bundle(vt_symbol, periods=periods)

    def get_or_sync(
        self,
        vt_symbol: str,
        *,
        years: int = 5,
        force: bool = False,
        periods: int = 12,
    ) -> tuple[FinancialBundle | None, FinancialSyncResult | None]:
        sync_result = sync_symbol_financials(vt_symbol, years=years, force=force)
        bundle = load_financial_bundle(vt_symbol, periods=periods)
        return bundle, sync_result
