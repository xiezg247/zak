"""行情采集部署模式（GUI 内 Scheduler vs 独立 collect 进程）。"""

from __future__ import annotations

import os

_EXTERNAL_MODES = frozenset({"external", "standalone", "outofprocess", "out-of-process"})


def quote_collect_mode() -> str:
    raw = os.getenv("ZAK_QUOTE_COLLECT_MODE", "").strip().lower()
    if raw in _EXTERNAL_MODES:
        return "external"
    if raw in {"embedded", "inline", "gui"}:
        return "embedded"
    return "embedded"


def quote_collect_external_enabled() -> bool:
    return quote_collect_mode() == "external"


def scheduler_collect_quotes_enabled() -> bool:
    """独立采集进程运行时，Leader Scheduler 不再调度 collect_quotes。"""
    return not quote_collect_external_enabled()
