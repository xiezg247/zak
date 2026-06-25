"""选股运行历史落库（PostgreSQL app schema）。"""

from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import Field, field_validator

from vnpy_ashare.domain.screener.result_row import ScreenerResultRow, coerce_screener_result_rows, screener_rows_to_dicts
from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.domain.base import MutableModel
from vnpy_common.storage.compat import DbRow
from vnpy_common.storage.tables import screener_runs as sr

_RUN_COLUMNS = (
    sr.c.id,
    sr.c.condition,
    sr.c.source,
    sr.c.row_count,
    sr.c.total_scanned,
    sr.c.config_json,
    sr.c.result_json,
    sr.c.created_at,
)


class ScreenerRunRecord(MutableModel):
    """单次选股运行记录。"""

    id: str = Field(description="运行记录 id")
    condition: str = Field(description="选股条件描述")
    source: str = Field(description="数据来源标识")
    row_count: int = Field(description="结果行数")
    total_scanned: int = Field(description="扫描标的总数")
    config: dict[str, Any] = Field(description="运行配置元数据")
    rows: list[ScreenerResultRow] = Field(description="选股结果行")
    created_at: str = Field(description="创建时间")

    @field_validator("rows", mode="before")
    @classmethod
    def _coerce_rows(cls, value: Any) -> list[ScreenerResultRow]:
        if value is None:
            return []
        return coerce_screener_result_rows(value)


def _now() -> str:
    return format_china_datetime()


def _row_to_record(row: DbRow) -> ScreenerRunRecord:
    return ScreenerRunRecord(
        id=str(row["id"]),
        condition=str(row["condition"]),
        source=str(row["source"]),
        row_count=int(row["row_count"]),
        total_scanned=int(row["total_scanned"]),
        config=json.loads(str(row["config_json"] or "{}")),
        rows=json.loads(str(row["result_json"] or "[]")),
        created_at=str(row["created_at"]),
    )


class ScreenerRunRepository(AppUserScopedRepository):
    table = sr

    def save_run(
        self,
        *,
        condition: str,
        source: str,
        rows: Sequence[ScreenerResultRow | Mapping[str, Any]],
        total_scanned: int = 0,
        config: dict[str, Any] | None = None,
    ) -> ScreenerRunRecord:
        run_id = uuid.uuid4().hex
        now = _now()
        normalized = coerce_screener_result_rows(rows)
        payload = json.dumps(screener_rows_to_dicts(normalized), ensure_ascii=False)
        config_payload = json.dumps(config or {}, ensure_ascii=False)
        self.insert_one_for_user(
            id=run_id,
            condition=condition,
            source=source,
            row_count=len(normalized),
            total_scanned=total_scanned,
            config_json=config_payload,
            result_json=payload,
            created_at=now,
        )
        return ScreenerRunRecord(
            id=run_id,
            condition=condition,
            source=source,
            row_count=len(normalized),
            total_scanned=total_scanned,
            config=config or {},
            rows=normalized,
            created_at=now,
        )

    def list_runs(self, *, limit: int = 20) -> list[ScreenerRunRecord]:
        rows = self.list_for_user(*_RUN_COLUMNS, order_by=(sr.c.created_at.desc(),), limit=limit)
        return [_row_to_record(row) for row in rows]

    def get_run(self, run_id: str) -> ScreenerRunRecord | None:
        rows = self.list_for_user(*_RUN_COLUMNS, extras=(sr.c.id == run_id,), limit=1)
        return _row_to_record(rows[0]) if rows else None

    def delete_run(self, run_id: str) -> bool:
        return self.delete_matching(self.scope(sr.c.id == run_id)) > 0

    def update_run_config(self, run_id: str, config: dict[str, Any]) -> bool:
        payload = json.dumps(config, ensure_ascii=False)
        return self.update_matching({"config_json": payload}, self.scope(sr.c.id == run_id)) > 0


_repo = ScreenerRunRepository()


def save_run(
    *,
    condition: str,
    source: str,
    rows: Sequence[ScreenerResultRow | Mapping[str, Any]],
    total_scanned: int = 0,
    config: dict[str, Any] | None = None,
) -> ScreenerRunRecord:
    """持久化选股结果并返回完整记录。"""
    return _repo.save_run(
        condition=condition,
        source=source,
        rows=rows,
        total_scanned=total_scanned,
        config=config,
    )


def list_runs(*, limit: int = 20) -> list[ScreenerRunRecord]:
    """按创建时间倒序列出历史运行。"""
    return _repo.list_runs(limit=limit)


def get_run(run_id: str) -> ScreenerRunRecord | None:
    """按 id 读取单次运行。"""
    return _repo.get_run(run_id)


def get_latest_run() -> ScreenerRunRecord | None:
    """最近一条运行记录。"""
    runs = list_runs(limit=1)
    return runs[0] if runs else None


def find_previous_run_by_recipe(
    recipe_id: str,
    *,
    exclude_run_id: str = "",
) -> ScreenerRunRecord | None:
    """查找同配方的上一次运行（按 created_at 倒序，跳过 exclude_run_id）。"""
    rid = recipe_id.strip()
    if not rid:
        return None
    for record in list_runs(limit=50):
        if exclude_run_id and record.id == exclude_run_id:
            continue
        if str(record.config.get("recipe_id", "")) == rid:
            return record
    return None


def find_previous_run_by_condition(
    condition: str,
    *,
    source: str = "",
    exclude_run_id: str = "",
) -> ScreenerRunRecord | None:
    """查找同 condition（可选 source）的上一次运行。"""
    label = (condition or "").strip()
    if not label:
        return None
    src = (source or "").strip()
    for record in list_runs(limit=50):
        if exclude_run_id and record.id == exclude_run_id:
            continue
        if record.condition != label:
            continue
        if src and record.source != src:
            continue
        return record
    return None


def delete_run(run_id: str) -> bool:
    """删除运行记录；成功返回 True。"""
    return _repo.delete_run(run_id)


def update_run_config(run_id: str, config: dict[str, Any]) -> bool:
    """更新运行的 config_json（如标记 read_at）。"""
    return _repo.update_run_config(run_id, config)


def mark_run_read(run_id: str) -> bool:
    """定时选股结果标记已读（写入 config.read_at）。"""
    record = get_run(run_id)
    if record is None:
        return False
    config = dict(record.config)
    if config.get("read_at"):
        return True
    config["read_at"] = _now()
    return update_run_config(run_id, config)


def is_auto_run(config: dict[str, Any]) -> bool:
    """是否为自动选股（定时 / AI / 配方）运行。"""
    trigger = str(config.get("trigger", ""))
    if trigger.startswith("scheduled_") or trigger.startswith("ai_"):
        return True
    if config.get("recipe_id"):
        return True
    return False


def is_strategy_run(config: dict[str, Any]) -> bool:
    """是否为策略选股页手动运行（非自动）。"""
    return not is_auto_run(config)


def is_run_unread(config: dict[str, Any]) -> bool:
    """定时运行且尚未标记 read_at。"""
    trigger = str(config.get("trigger", ""))
    return trigger.startswith("scheduled_") and not config.get("read_at")
