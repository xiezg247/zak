"""选股运行结果对比（同配方上次 run）。"""

from __future__ import annotations

from typing import Any, Literal

DiffStatus = Literal["新增", "保留", ""]


def symbol_set(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row.get("vt_symbol") or "").strip() for row in rows if row.get("vt_symbol")}


def compute_run_diff(
    current_rows: list[dict[str, Any]],
    previous_rows: list[dict[str, Any]],
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
    rows: list[dict[str, Any]],
    recipe_id: str,
    config: dict[str, Any],
) -> list[dict[str, Any]]:
    """同配方对比上次 run，写入 config.run_diff 与行级 diff_status。"""
    rid = (recipe_id or "").strip()
    if not rid:
        return rows
    from vnpy_ashare.screener.run.run_store import find_previous_run_by_recipe

    previous = find_previous_run_by_recipe(rid)
    if previous is None:
        return rows
    diff = compute_run_diff(rows, previous.rows)
    config["run_diff"] = {
        "previous_run_id": previous.id,
        "new_count": diff["new_count"],
        "stay_count": diff["stay_count"],
        "drop_count": diff["drop_count"],
    }
    return annotate_rows_with_diff(rows, diff)


def annotate_rows_with_diff(
    rows: list[dict[str, Any]],
    diff: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """为当前结果行写入 ``diff_status``（新增/保留）。"""
    if not diff:
        return rows
    new_set = set(diff.get("new") or [])
    stay_set = set(diff.get("stay") or [])
    annotated: list[dict[str, Any]] = []
    for row in rows:
        merged = dict(row)
        vt = str(merged.get("vt_symbol") or "")
        if vt in new_set:
            merged["diff_status"] = "新增"
        elif vt in stay_set:
            merged["diff_status"] = "保留"
        else:
            merged["diff_status"] = ""
        annotated.append(merged)
    return annotated
