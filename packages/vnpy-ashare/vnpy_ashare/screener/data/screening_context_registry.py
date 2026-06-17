"""选股 ContextVar 注册表（打破 screening_context ↔ history_signals 循环）。"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Any

_screening_ctx: ContextVar[Any] = ContextVar("screening_ctx", default=None)


def get_screening_context() -> Any:
    return _screening_ctx.get()


def activate_screening_context(ctx: Any) -> Token[Any]:
    return _screening_ctx.set(ctx)


def deactivate_screening_context(token: Token[Any]) -> None:
    _screening_ctx.reset(token)
