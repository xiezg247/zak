"""运行时热路径耗时 tracing（``ZAK_PERF_TRACE=1`` 启用）。"""

from __future__ import annotations

import logging
import os
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

logger = logging.getLogger("perf")

_TRUTHY = frozenset({"1", "true", "yes", "on"})

_env_loaded = False


def _load_env() -> None:
    global _env_loaded
    if _env_loaded:
        return
    from dotenv import load_dotenv

    from vnpy_common.paths import ENV_FILE

    if ENV_FILE.is_file():
        load_dotenv(ENV_FILE, override=False)
    _env_loaded = True


def perf_trace_enabled() -> bool:
    _load_env()
    return os.environ.get("ZAK_PERF_TRACE", "").strip().lower() in _TRUTHY


def _ensure_logging() -> None:
    if logger.handlers:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


@dataclass
class PerfTracer:
    _enabled: bool | None = field(default=None, init=False, repr=False)
    _records: list[tuple[str, float]] = field(default_factory=list, init=False)

    @property
    def enabled(self) -> bool:
        if self._enabled is None:
            self._enabled = perf_trace_enabled()
            if self._enabled:
                _ensure_logging()
        return self._enabled

    @contextmanager
    def trace(self, name: str) -> Iterator[None]:
        if not self.enabled:
            yield
            return
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._records.append((name, elapsed_ms))
            logger.info("%s %.0fms", name, elapsed_ms)

    def record(self, name: str, elapsed_ms: float) -> None:
        if not self.enabled:
            return
        self._records.append((name, elapsed_ms))
        logger.info("%s %.0fms", name, elapsed_ms)

    def summary(self, label: str = "perf summary", *, top_n: int = 10) -> None:
        if not self.enabled or not self._records:
            return
        total_ms = sum(ms for _, ms in self._records)
        logger.info("%s %.0fms (%d spans)", label, total_ms, len(self._records))
        if len(self._records) > 1:
            ranked = sorted(self._records, key=lambda item: item[1], reverse=True)
            parts = ", ".join(f"{name} {ms:.0f}ms" for name, ms in ranked[:top_n])
            logger.info("perf slowest: %s", parts)

    def reset(self) -> None:
        self._records.clear()


tracer = PerfTracer()
