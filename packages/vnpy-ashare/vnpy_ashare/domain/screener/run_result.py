"""选股执行结果领域模型。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import Field, field_validator

from vnpy_ashare.domain.screener.result_row import (
    ScreenerResultRow,
    ScreeningRowLike,
    coerce_screener_result_rows,
)
from vnpy_common.domain.base import MutableModel


class ScreenerRunResult(MutableModel):
    """单次选股执行结果。"""

    rows: list[ScreenerResultRow] = Field(description="选股结果行")
    condition: str = Field(description="选股条件描述")
    updated_at: str | None = Field(description="数据更新时间")
    total_scanned: int = Field(description="扫描标的总数")
    source: str = Field(description="数据来源标识")
    columns: list[tuple[str, str]] = Field(default_factory=list, description="导出列定义")

    @field_validator("rows", mode="before")
    @classmethod
    def _coerce_rows(cls, value: Any) -> list[ScreenerResultRow]:
        if value is None:
            return []
        return coerce_screener_result_rows(value)


def build_screener_run_result(
    *,
    rows: Sequence[ScreeningRowLike],
    condition: str,
    updated_at: str | None,
    total_scanned: int,
    source: str,
    columns: Sequence[tuple[str, str]] | None = None,
) -> ScreenerRunResult:
    """构造选股结果（内部 dict 行自动转为 ``ScreenerResultRow``）。"""
    normalized = coerce_screener_result_rows(rows)
    resolved_columns = list(columns) if columns is not None else _resolve_export_columns(normalized)
    return ScreenerRunResult(
        rows=normalized,
        condition=condition,
        updated_at=updated_at,
        total_scanned=total_scanned,
        source=source,
        columns=resolved_columns,
    )


def _resolve_export_columns(rows: list[ScreenerResultRow]) -> list[tuple[str, str]]:
    from vnpy_ashare.screener.run.export import resolve_export_columns  # noqa: PLC0415

    return resolve_export_columns(rows)
