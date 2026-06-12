"""AI 上下文 pytest fixture。"""

from __future__ import annotations

import pytest

from vnpy_ashare.ai.context import clear_all


@pytest.fixture(autouse=True)
def _reset_ai_context_store() -> None:
    clear_all()
    yield
    clear_all()
