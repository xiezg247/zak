"""选股执行结果类型（打破 runner ↔ industry_screen 循环）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ScreenerRunResult:
    """单次选股执行结果。"""

    rows: list[dict[str, Any]]
    condition: str
    updated_at: str | None
    total_scanned: int
    source: str
    columns: list[tuple[str, str]] = field(default_factory=list)
