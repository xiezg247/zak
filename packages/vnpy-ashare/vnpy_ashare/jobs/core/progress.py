"""定时任务执行过程日志（供调度器 UI 实时展示）。"""

from __future__ import annotations

from collections.abc import Callable
from contextvars import ContextVar, Token

_log_sink: ContextVar[Callable[[str], None] | None] = ContextVar("ashare_job_log_sink", default=None)


def bind_job_log(sink: Callable[[str], None]) -> Callable[[], None]:
    """绑定当前任务线程的日志输出；返回 reset 函数。"""
    token: Token = _log_sink.set(sink)

    def reset() -> None:
        _log_sink.reset(token)

    return reset


def job_log(message: str) -> None:
    """向当前任务的执行日志追加一行（无绑定时静默忽略）。"""
    text = str(message).strip()
    if not text:
        return
    sink = _log_sink.get()
    if sink is not None:
        sink(text)


def job_progress(current: int, total: int, label: str = "") -> None:
    """格式化进度并写入任务日志（大批量任务自动抽样，避免 UI 刷新风暴）。"""
    if total <= 0:
        return
    if current <= 1 or current >= total:
        emit = True
    elif total <= 25:
        emit = True
    else:
        step = max(1, total // 40)
        emit = current % step == 0
    if not emit:
        return
    prefix = f"{label} " if label else ""
    job_log(f"{prefix}({current}/{total})")
