"""短线工作流：自选池批量写入与 AI 快照（信号区 + 共振）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.config.preferences.watchlist_groups import load_active_watchlist_group_id
from vnpy_ashare.config.preferences.watchlist_signal import load_signal_panel_symbols
from vnpy_ashare.domain.symbols.stock import parse_stock_symbol
from vnpy_ashare.quotes.radar.radar_loaders import RadarCardData, RadarRow
from vnpy_ashare.quotes.radar.radar_resonance_store import (
    get_radar_resonance_entries,
    radar_resonance_updated_at,
)
from vnpy_ashare.services.watchlist import WatchlistService
from vnpy_ashare.storage.repositories.trading_plans import load_active_trading_plan
from vnpy_ashare.trading.risk.realized_pnl import today_trade_date
from vnpy_common.domain.base import FrozenModel


class WatchlistPoolBatchResult(FrozenModel):
    watchlist_added: int = Field(description="新增至自选数")
    skipped: int = Field(description="跳过数量")


def add_rows_to_watchlist_pool(
    service: WatchlistService,
    rows: tuple[RadarRow, ...] | list[RadarRow],
) -> WatchlistPoolBatchResult:
    """确保标的在自选池（不写入分组）。"""
    watchlist_added = skipped = 0
    for row in rows:
        item = parse_stock_symbol(row.vt_symbol)
        if item is None:
            skipped += 1
            continue
        name = row.name or item.name
        if service.add(item.symbol, item.exchange, name):
            watchlist_added += 1
        elif service.add_failure_reason(item.symbol, item.exchange) == "full":
            skipped += 1
            break
        else:
            skipped += 1
    return WatchlistPoolBatchResult(watchlist_added=watchlist_added, skipped=skipped)


def collect_dragon_1_rows(payload: dict[str, RadarCardData]) -> tuple[RadarRow, ...]:
    data = payload.get("leader_pick")
    if data is None:
        return ()
    return tuple(row for row in data.rows if row.leader_tier == "dragon_1")


def build_short_term_watchlist_snapshot(
    service: WatchlistService,
    *,
    resonance_top_n: int = 5,
) -> dict[str, object]:
    """信号区名单 + 激活交易计划 + 雷达共振 Top N。"""
    top_n = max(1, min(int(resonance_top_n), 20))
    items_by_key = {(row["symbol"], row["exchange"]): row for row in service.get_items()}

    signal_symbols: list[dict[str, str]] = []
    for vt_symbol in load_signal_panel_symbols():
        parsed = parse_stock_symbol(vt_symbol)
        if parsed is None:
            continue
        key = (parsed.symbol, parsed.exchange.name)
        item = items_by_key.get(key, {})
        signal_symbols.append(
            {
                "vt_symbol": vt_symbol,
                "symbol": parsed.symbol,
                "name": str(item.get("name") or parsed.name),
                "exchange": parsed.exchange.name,
            }
        )

    plan_symbols: list[dict[str, str]] = []
    plan = load_active_trading_plan(today_trade_date())
    if plan is not None:
        for item in plan.symbols:
            vt = item.vt_symbol
            plan_symbols.append(
                {
                    "vt_symbol": vt,
                    "symbol": item.symbol,
                    "name": item.symbol,
                    "exchange": item.exchange,
                }
            )

    resonance_top = [
        {
            "vt_symbol": entry.vt_symbol,
            "name": entry.name,
            "card_count": entry.card_count,
            "resonance_score": entry.resonance_score,
            "card_titles": list(entry.card_titles),
        }
        for entry in get_radar_resonance_entries()[:top_n]
    ]

    active_group_id = load_active_watchlist_group_id()
    active_group_name = ""
    if active_group_id:
        for group in service.list_groups():
            if group.id == active_group_id:
                active_group_name = group.name
                break

    return {
        "signal_panel_symbols": signal_symbols,
        "signal_panel_count": len(signal_symbols),
        "active_plan_trade_date": plan.trade_date if plan is not None else None,
        "active_plan_symbols": plan_symbols,
        "active_plan_count": len(plan_symbols),
        "resonance_top_n": top_n,
        "resonance_symbols": resonance_top,
        "resonance_updated_at": radar_resonance_updated_at(),
        "active_watchlist_group_id": active_group_id,
        "active_watchlist_group": active_group_name,
    }


def _radar_row_from_screener_dict(row: dict) -> RadarRow | None:
    vt_symbol = str(row.get("vt_symbol") or "").strip()
    if not vt_symbol:
        return None
    item = parse_stock_symbol(vt_symbol)
    name = str(row.get("name") or (item.name if item else "") or vt_symbol)
    symbol = str(row.get("symbol") or (item.symbol if item else vt_symbol.split(".")[0]))
    return RadarRow(
        vt_symbol=vt_symbol,
        name=name,
        symbol=symbol,
        price=None,
        change_pct=None,
        metric_label="",
        metric_value="",
        sub_label="",
        sub_value="",
    )


def add_screener_rows_to_watchlist_pool(
    service: WatchlistService,
    rows: list[dict],
) -> WatchlistPoolBatchResult:
    parsed: list[RadarRow] = []
    for row in rows:
        item = _radar_row_from_screener_dict(row)
        if item is not None:
            parsed.append(item)
    return add_rows_to_watchlist_pool(service, parsed)
