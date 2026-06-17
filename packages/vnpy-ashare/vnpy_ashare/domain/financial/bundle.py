"""个股财报同步与查询领域模型。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_ashare.storage.repositories.financial import FinancialSnapshotRow, FinancialSyncMeta
from vnpy_common.domain.base import MutableModel


class FinancialSyncResult(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    synced: bool = Field(description="是否同步成功")
    skipped: bool = Field(default=False, description="是否跳过同步")
    message: str = Field(default="", description="说明信息")
    periods_written: int = Field(default=0, description="写入报告期数")
    warnings: list[str] = Field(default_factory=list, description="警告信息")


class FinancialBundle(MutableModel):
    ts_code: str = Field(description="Tushare 代码")
    vt_symbol: str = Field(description="合约代码（含交易所）")
    name: str = Field(description="名称")
    sync_meta: FinancialSyncMeta | None = Field(description="同步元数据")
    snapshots: list[FinancialSnapshotRow] = Field(description="财报快照列表")
    reports: dict[str, list[dict[str, Any]]] = Field(description="原始报告")
