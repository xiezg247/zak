"""任务执行结果。"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from vnpy_common.domain.base import MutableModel


class JobResult(MutableModel):
    success: bool = Field(description="任务是否成功")
    message: str = Field(description="结果说明")
    skipped: bool = Field(default=False, description="是否跳过执行")
    finished_at: datetime = Field(default_factory=datetime.now, description="完成时间")
