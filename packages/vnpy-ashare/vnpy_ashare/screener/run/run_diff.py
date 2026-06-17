"""选股运行结果对比（同配方上次 run）。"""

from __future__ import annotations

from typing import Any, Literal

from vnpy_ashare.domain.market.quote_row import QuoteRow, coerce_quote_row
from vnpy_ashare.screener.run.run_store import find_previous_run_by_condition, find_previous_run_by_recipe

DiffStatus = Literal["新增", "保留", ""]


def symbol_set(rows: list[QuoteRow]) -> set[str]:
    return {str(row.get("vt_symbol") or "").strip() for row in rows if row.get("vt_symbol")}


def compute_run_diff(
    current_rows: list[QuoteRow],
    previous_rows: list[QuoteRow],
) -> dict[str, Any]:
    """对比两次结果的 vt_symbol 集合。"""
    current = symbol_set(current_rows)
    previous = symbol_set(previous_rows)
    new_symbols = sorted(current - previous)
    stay_symbols = sorted(current & previous)
    drop_symbols = sorted(previous - current)
    return {
        "new": new_symbols,
        "stay": stay_symbols,
        "drop": drop_symbols,
        "new_count": len(new_symbols),
        "stay_count": len(stay_symbols),
        "drop_count": len(drop_symbols),
        "previous_count": len(previous),
        "current_count": len(current),
    }


def enrich_recipe_run(
    rows: list[QuoteRow],
    recipe_id: str,
    config: dict[str, Any],
) -> list[QuoteRow]:
    """同配方对比上次 run，写入 config.run_diff 与行级 diff_status。"""
    rid = (recipe_id or "").strip()
    if not rid:
        return [coerce_quote_row(row) for row in rows]

    previous = find_previous_run_by_recipe(rid)
    if previous is None:
        return [coerce_quote_row(row) for row in rows]
    diff = compute_run_diff(rows, previous.rows)
    config["run_diff"] = {
        "previous_run_id": previous.id,
        "new_count": diff["new_count"],
        "stay_count": diff["stay_count"],
        "drop_count": diff["drop_count"],
    }
    return annotate_rows_with_diff(rows, diff)


def enrich_condition_run(
    rows: list[QuoteRow],
    condition: str,
    config: dict[str, Any],
    *,
    source: str = "",
) -> list[QuoteRow]:
    """同 condition 对比上次 run（雷达共振 / 行业成分等）。"""
    label = (condition or "").strip()
    if not label:
        return [coerce_quote_row(row) for row in rows]

    previous = find_previous_run_by_condition(label, source=source)
    if previous is None:
        return [coerce_quote_row(row) for row in rows]
    diff = compute_run_diff(rows, previous.rows)
    config["run_diff"] = {
        "previous_run_id": previous.id,
        "new_count": diff["new_count"],
        "stay_count": diff["stay_count"],
        "drop_count": diff["drop_count"],
    }
    return annotate_rows_with_diff(rows, diff)


def annotate_rows_with_diff(
    rows: list[QuoteRow],
    diff: dict[str, Any] | None,
) -> list[QuoteRow]:
    """为当前结果行写入 ``diff_status``（新增/保留）。"""
    if not diff:
        return [coerce_quote_row(row) for row in rows]
    new_set = set(diff.get("new") or [])
    stay_set = set(diff.get("stay") or [])
    annotated: list[QuoteRow] = []
    for row in rows:
        normalized = coerce_quote_row(row)
        vt = str(normalized.get("vt_symbol") or "")
        if vt in new_set:
            status: DiffStatus = "新增"
        elif vt in stay_set:
            status = "保留"
        else:
            status = ""
        annotated.append(normalized.model_copy(update={"diff_status": status}))
    return annotated
