"""Tushare 资金流类型标注测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.market.moneyflow_kind import classify_moneyflow_row, flow_kind_label


def test_classify_main_force_from_net_mf_and_large_orders() -> None:
    kind = classify_moneyflow_row(
        {
            "net_mf_amount": 12000,
            "buy_elg_amount": 8000,
            "sell_elg_amount": 1000,
            "buy_lg_amount": 5000,
            "sell_lg_amount": 2000,
            "buy_md_amount": 3000,
            "sell_md_amount": 2500,
            "change_pct": 4.0,
            "turnover_rate": 6.0,
        }
    )
    assert kind == "main"
    assert flow_kind_label(kind) == "主力"


def test_classify_active_from_medium_orders_and_turnover() -> None:
    kind = classify_moneyflow_row(
        {
            "net_mf_amount": 500,
            "buy_elg_amount": 1000,
            "sell_elg_amount": 3000,
            "buy_lg_amount": 2000,
            "sell_lg_amount": 4000,
            "buy_md_amount": 8000,
            "sell_md_amount": 2000,
            "change_pct": 5.0,
            "turnover_rate": 8.0,
        }
    )
    assert kind == "active"
    assert flow_kind_label(kind) == "活跃"


def test_classify_proxy_when_flagged() -> None:
    kind = classify_moneyflow_row({"moneyflow_proxy": True, "net_mf_amount": 99999})
    assert kind == "proxy"
    assert flow_kind_label(kind) == "代理"


def test_flow_kind_score_factors() -> None:
    from vnpy_ashare.quotes.market.moneyflow_kind import (
        moneyflow_dimension_score_factor,
        row_flow_kind,
    )

    assert moneyflow_dimension_score_factor("momentum", {"flow_kind": "proxy"}) == 1.0
    assert moneyflow_dimension_score_factor("moneyflow", {"flow_kind": "main"}) == 1.1
    assert moneyflow_dimension_score_factor("moneyflow_intraday", {"moneyflow_proxy": True}) == 0.7
    assert row_flow_kind({"buy_md_amount": 100, "change_pct": 5, "turnover_rate": 8}) == "active"
