"""选股运行记录查找（供盘中快照复用）。"""

from __future__ import annotations

from vnpy_ashare.screener.run.run_store import ScreenerRunRecord, is_auto_run, is_strategy_run, list_runs


def find_run_for_task_variant(variant: str) -> ScreenerRunRecord | None:
    if variant == "strategy":
        for record in list_runs(limit=30):
            if is_strategy_run(record.config):
                return record
        return None
    trigger = f"scheduled_{variant.removeprefix('scheduled_')}"
    for record in list_runs(limit=30):
        if not is_auto_run(record.config):
            continue
        if str(record.config.get("trigger", "")) == trigger:
            return record
    return None
