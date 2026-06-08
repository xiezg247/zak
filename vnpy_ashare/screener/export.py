"""选股结果导出 CSV。"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

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

_MONEYFLOW_COLUMNS = [
    ("symbol", "代码"),
    ("name", "名称"),
    ("vt_symbol", "合约"),
    ("net_mf_amount", "主力净流入(万)"),
    ("buy_elg_amount", "特大单买入(万)"),
    ("sell_elg_amount", "特大单卖出(万)"),
    ("trade_date", "交易日"),
]


def resolve_export_columns(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    if not rows:
        return _QUOTE_COLUMNS
    source = str(rows[0].get("source", "quote"))
    if "net_mf_amount" in rows[0]:
        return _MONEYFLOW_COLUMNS
    if source == "tushare" or "pe_ttm" in rows[0]:
        return _FUNDAMENTAL_COLUMNS
    return _QUOTE_COLUMNS


def export_rows_to_csv(rows: list[dict[str, Any]], path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    columns = resolve_export_columns(rows)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow([label for _, label in columns])
        for row in rows:
            writer.writerow([row.get(key, "") for key, _ in columns])
    return target
