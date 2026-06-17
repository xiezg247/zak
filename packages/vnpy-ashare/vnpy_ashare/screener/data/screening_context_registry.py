"""选股 ContextVar 注册表（打破 screening_context ↔ history_signals 循环）。"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vnpy_ashare.screener.data.screening_context import ScreeningContext

_screening_ctx: ContextVar[ScreeningContext | None] = ContextVar("screening_ctx", default=None)


def get_screening_context() -> ScreeningContext | None:
    return _screening_ctx.get()


def activate_screening_context(ctx: ScreeningContext) -> Token[ScreeningContext | None]:
    return _screening_ctx.set(ctx)


def deactivate_screening_context(token: Token[ScreeningContext | None]) -> None:
    _screening_ctx.reset(token)
