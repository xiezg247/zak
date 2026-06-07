"""任务执行结果。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class JobResult:
    success: bool
    message: str
    skipped: bool = False
    finished_at: datetime = field(default_factory=datetime.now)
