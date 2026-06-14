"""Tushare 资金流类型标注（主力 / 活跃 / 代理）。"""

from __future__ import annotations

from typing import Any, Literal

FlowKind = Literal["main", "active", "proxy"]

FLOW_KIND_LABELS: dict[FlowKind, str] = {
    "main": "主力",
    "active": "活跃",
    "proxy": "代理",
}

_ACTIVE_MIN_CHANGE_PCT = 2.0
_ACTIVE_MIN_TURNOVER = 3.0


def flow_kind_label(kind: str | None) -> str:
    if kind in FLOW_KIND_LABELS:
        return FLOW_KIND_LABELS[kind]  # type: ignore[index]
    return FLOW_KIND_LABELS["main"]


def classify_moneyflow_row(row: dict[str, Any]) -> FlowKind:
    """基于 Tushare 档位与数据来源标注资金类型。"""
    explicit = str(row.get("flow_kind") or "").strip()
    if explicit in FLOW_KIND_LABELS:
        return explicit  # type: ignore[return-value]

    if row.get("moneyflow_proxy"):
        return "proxy"

    reason = str(row.get("reason") or row.get("hit_reason") or "")
    if "代理" in reason:
        return "proxy"

    net_mf = float(row.get("net_mf_amount") or 0)
    buy_elg = float(row.get("buy_elg_amount") or 0)
    sell_elg = float(row.get("sell_elg_amount") or 0)
    buy_lg = float(row.get("buy_lg_amount") or 0)
    sell_lg = float(row.get("sell_lg_amount") or 0)
    buy_md = float(row.get("buy_md_amount") or 0)
    sell_md = float(row.get("sell_md_amount") or 0)

    main_order_net = (buy_elg + buy_lg) - (sell_elg + sell_lg)
    md_net = buy_md - sell_md
    change = float(row.get("change_pct") or row.get("pct_chg") or 0)
    turnover = float(row.get("turnover_rate") or 0)

    has_buckets = any(value > 0 for value in (buy_elg, sell_elg, buy_lg, sell_lg, buy_md, sell_md))
    if has_buckets:
        if net_mf > 0 and main_order_net >= md_net:
            return "main"
        if md_net > 0 and change >= _ACTIVE_MIN_CHANGE_PCT and turnover >= _ACTIVE_MIN_TURNOVER:
            return "active"
        if net_mf > 0:
            return "main"
        if md_net > 0:
            return "active"
        return "proxy"

    if net_mf > 0:
        return "main"
    if change >= _ACTIVE_MIN_CHANGE_PCT and turnover >= _ACTIVE_MIN_TURNOVER:
        return "active"
    return "proxy"


def enrich_moneyflow_row_with_kind(row: dict[str, Any]) -> dict[str, Any]:
    item = dict(row)
    item["flow_kind"] = classify_moneyflow_row(item)
    return item
