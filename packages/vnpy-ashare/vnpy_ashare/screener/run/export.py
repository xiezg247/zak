"""选股结果导出 CSV。

``resolve_export_columns`` 按 source / 字段自动选择行情、基本面、资金流或配方列集。
"""

from __future__ import annotations

import csv
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRowLike, quote_row_as_dict

_QUOTE_COLUMNS = [
    ("symbol", "代码"),
    ("name", "名称"),
    ("vt_symbol", "合约"),
    ("last_price", "现价"),
    ("change_pct", "涨幅%"),
    ("turnover_rate", "换手%"),
    ("volume", "成交量"),
]

_FUNDAMENTAL_COLUMNS = [
    ("symbol", "代码"),
    ("name", "名称"),
    ("vt_symbol", "合约"),
    ("close", "收盘价"),
    ("pe_ttm", "PE TTM"),
    ("pb", "PB"),
    ("total_mv", "总市值(万)"),
    ("circ_mv", "流通市值(万)"),
    ("turnover_rate", "换手%"),
    ("trade_date", "交易日"),
]

_RECIPE_COLUMNS = [
    ("symbol", "代码"),
    ("name", "名称"),
    ("vt_symbol", "合约"),
    ("diff_status", "变动"),
    ("composite_score", "综合分"),
    ("hit_reason", "入选原因"),
    ("industry", "行业"),
    ("change_pct", "涨幅%"),
    ("turnover_rate", "换手%"),
    ("volume_ratio", "量比"),
    ("pe_ttm", "PE TTM"),
    ("net_mf_amount", "主力净流入(万)"),
    ("flow_kind", "资金类型"),
]

_MONEYFLOW_COLUMNS = [
    ("symbol", "代码"),
    ("name", "名称"),
    ("vt_symbol", "合约"),
    ("net_mf_amount", "主力净流入(万)"),
    ("flow_kind", "资金类型"),
    ("buy_elg_amount", "特大单买入(万)"),
    ("sell_elg_amount", "特大单卖出(万)"),
    ("trade_date", "交易日"),
]


_FUNDAMENTAL_FIELD_KEYS = ("close", "pe_ttm", "pb", "total_mv", "circ_mv", "trade_date")


def _has_fundamental_display_data(rows: list[QuoteRowLike]) -> bool:
    sample = rows[: min(5, len(rows))]
    return any(row.get(key) not in (None, "") for row in sample for key in _FUNDAMENTAL_FIELD_KEYS)


def _is_moneyflow_primary_rows(rows: list[QuoteRowLike]) -> bool:
    """资金流 preset 结果（非行情 preset 附带补全的 net_mf_amount）。"""
    row = rows[0]
    if row.get("moneyflow_source"):
        return True
    return "net_mf_amount" in row and "last_price" not in row


def resolve_export_columns(rows: list[QuoteRowLike]) -> list[tuple[str, str]]:
    """根据首行字段推断导出列（field_key, 中文标题）。"""
    if not rows:
        return _QUOTE_COLUMNS
    if "hit_reason" in rows[0] or "composite_score" in rows[0]:
        optional = {"diff_status", "industry", "volume_ratio", "pe_ttm", "net_mf_amount", "flow_kind"}
        columns = [col for col in _RECIPE_COLUMNS if col[0] not in optional or any(col[0] in row for row in rows[: min(5, len(rows))])]
        return columns or _RECIPE_COLUMNS
    if _is_moneyflow_primary_rows(rows):
        return _MONEYFLOW_COLUMNS
    if _has_fundamental_display_data(rows):
        return _FUNDAMENTAL_COLUMNS
    return _QUOTE_COLUMNS


def export_rows_to_csv(rows: list[QuoteRowLike], path: str | Path) -> Path:
    """将选股结果写入 UTF-8 BOM CSV，返回目标路径。"""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    columns = resolve_export_columns(rows)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([label for _, label in columns])
        for row in rows:
            payload = quote_row_as_dict(row)
            writer.writerow([payload.get(key, "") for key, _ in columns])
    return target
