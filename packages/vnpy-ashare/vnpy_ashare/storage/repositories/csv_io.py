"""CSV 读写辅助（自选 / universe 导入导出）。"""

from __future__ import annotations

import csv
from pathlib import Path

from vnpy.trader.constant import Exchange


def read_stock_csv_rows(path: Path) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    with path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            items.append(
                {
                    "symbol": row["symbol"].strip(),
                    "exchange": row["exchange"].strip().upper(),
                    "name": row.get("name", "").strip(),
                }
            )
    return items


def write_stock_csv(
    path: Path,
    items: list[tuple[str, Exchange, str]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["symbol", "exchange", "name"])
        for symbol, exchange, name in items:
            writer.writerow([symbol, exchange.name, name])
