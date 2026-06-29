"""QuoteRow / dict 行 ↔ Polars DataFrame 桥接。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from vnpy_ashare.domain.market.quote_row import QuoteRow, coerce_quote_row


def row_to_dict(row: Any) -> dict[str, Any]:
    if isinstance(row, QuoteRow):
        return row.to_dict()
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "to_dict"):
        return dict(row.to_dict())
    raise TypeError(f"不支持的选股行类型: {type(row)!r}")


def rows_with_index(rows: Sequence[Any]) -> tuple[list[dict[str, Any]], list[int]]:
    """为每行附加 ``_row_idx``，便于过滤后还原原始对象。"""
    payloads: list[dict[str, Any]] = []
    indices: list[int] = []
    for index, row in enumerate(rows):
        payload = row_to_dict(row)
        payload["_row_idx"] = index
        payloads.append(payload)
        indices.append(index)
    return payloads, indices


def restore_rows(rows: Sequence[Any], filtered_payloads: list[dict[str, Any]]) -> list[Any]:
    kept: list[Any] = []
    for payload in filtered_payloads:
        index = int(payload.get("_row_idx", -1))
        if 0 <= index < len(rows):
            kept.append(rows[index])
    return kept


def dicts_to_quote_rows(dicts: list[dict[str, Any]]) -> list[QuoteRow]:
    return [coerce_quote_row({k: v for k, v in item.items() if k != "_row_idx"}) for item in dicts]
