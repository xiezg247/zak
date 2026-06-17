"""次日计划草案（J-03 MVP）。"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from vnpy.trader.constant import Exchange

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.services.watchlist_short_term import (
    SHORT_TERM_OBSERVATION_GROUP_NAME,
    build_short_term_watchlist_snapshot,
    ensure_short_term_observation_group,
)
from vnpy_ashare.storage.repositories.trading_plans import (
    activate_trading_plan,
    create_trading_plan,
    load_trading_plan,
    replace_trading_plan_symbols,
)
from vnpy_ashare.storage.repositories.watchlist_groups import load_watchlist_groups


def _next_trade_date(from_day: date | None = None) -> str:
    day = from_day or datetime.now(CHINA_TZ).date()
    return (day + timedelta(days=1)).isoformat()


def build_trading_plan_draft(
    *,
    watchlist_service=None,
    trade_date: str | None = None,
) -> dict[str, Any]:
    """基于情绪周期 + 短线观察组生成计划草案（不写入 DB）。"""
    emotion = load_emotion_cycle_snapshot(fetch_if_missing=True)
    target_date = trade_date or _next_trade_date()
    max_position_pct = 0.0
    emotion_expected = ""
    if emotion is not None:
        emotion_expected = emotion.stage
        max_position_pct = emotion.position_pct_max

    symbols: list[dict[str, str]] = []
    if watchlist_service is not None:
        snapshot = build_short_term_watchlist_snapshot(watchlist_service, resonance_top_n=5)
        for item in snapshot.get("observation_symbols", []):
            if isinstance(item, dict):
                symbols.append(
                    {
                        "vt_symbol": str(item.get("vt_symbol") or ""),
                        "symbol": str(item.get("symbol") or ""),
                        "exchange": str(item.get("exchange") or ""),
                        "name": str(item.get("name") or ""),
                    }
                )
        resonance = snapshot.get("resonance_symbols") or []
        seen = {item["vt_symbol"] for item in symbols if item.get("vt_symbol")}
        for item in resonance:
            if not isinstance(item, dict):
                continue
            vt = str(item.get("vt_symbol") or "")
            if not vt or vt in seen:
                continue
            parsed = parse_stock_symbol(vt)
            if parsed is None:
                continue
            symbols.append(
                {
                    "vt_symbol": vt,
                    "symbol": parsed.symbol,
                    "exchange": parsed.exchange.name,
                    "name": str(item.get("name") or parsed.name),
                }
            )
            seen.add(vt)
            if len(symbols) >= 5:
                break

    groups = load_watchlist_groups()
    observation_group_id = next(
        (group.id for group in groups if group.name == SHORT_TERM_OBSERVATION_GROUP_NAME),
        None,
    )

    return {
        "trade_date": target_date,
        "emotion_expected": emotion_expected,
        "emotion_stage_label": emotion.stage_label if emotion is not None else "",
        "max_position_pct": max_position_pct,
        "watchlist": symbols[:5],
        "observation_group_name": SHORT_TERM_OBSERVATION_GROUP_NAME,
        "observation_group_id": observation_group_id,
        "notes": "AI/系统草案：请确认后再激活",
        "status": "draft",
    }


def persist_trading_plan_draft(
    draft: dict[str, Any],
    *,
    activate: bool = False,
) -> str | None:
    trade_date = str(draft.get("trade_date") or "")
    if not trade_date:
        return None
    plan_id = create_trading_plan(
        trade_date=trade_date,
        emotion_expected=str(draft.get("emotion_expected") or ""),
        max_position_pct=float(draft.get("max_position_pct") or 0),
        notes=str(draft.get("notes") or ""),
        status="draft",
    )
    if plan_id is None:
        return None
    symbol_rows: list[tuple[str, Exchange]] = []
    for item in draft.get("watchlist") or []:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip()
        exchange_name = str(item.get("exchange") or "").strip()
        if not symbol or not exchange_name:
            vt = str(item.get("vt_symbol") or "")
            parsed = parse_stock_symbol(vt)
            if parsed is None:
                continue
            symbol_rows.append((parsed.symbol, parsed.exchange))
            continue
        try:
            exchange = Exchange(exchange_name)
        except ValueError:
            continue
        symbol_rows.append((symbol, exchange))
    replace_trading_plan_symbols(plan_id, symbol_rows)
    if activate:
        activate_trading_plan(plan_id)
    return plan_id


def sync_plan_to_observation_group(plan_id: str, watchlist_service) -> int:
    plan = load_trading_plan(plan_id)
    if plan is None or watchlist_service is None:
        return 0
    group_id, _ = ensure_short_term_observation_group(watchlist_service)
    if group_id is None:
        return 0
    added = 0
    for item in plan.symbols:
        try:
            exchange = Exchange(item.exchange)
        except ValueError:
            continue
        if watchlist_service.add(item.symbol, exchange, item.symbol):
            pass
        if watchlist_service.add_to_group(group_id, item.symbol, exchange):
            added += 1
    return added
