"""启动分段耗时 profiling（``ZAK_STARTUP_PROFILE=1`` 启用）。"""

from __future__ import annotations

import logging
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

logger = logging.getLogger("startup")

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


def startup_profile_enabled() -> bool:
    _load_env()
    return os.environ.get("ZAK_STARTUP_PROFILE", "").strip().lower() in _TRUTHY


def _ensure_logging() -> None:
    if logging.root.handlers:
        if not logger.isEnabledFor(logging.INFO):
            logger.setLevel(logging.INFO)
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )


@dataclass
class StartupProfiler:
    _enabled: bool | None = field(default=None, init=False, repr=False)
    _origin: float = field(default=0.0, init=False)
    _records: list[tuple[str, float]] = field(default_factory=list, init=False)

    @property
    def enabled(self) -> bool:
        if self._enabled is None:
            self._enabled = startup_profile_enabled()
            if self._enabled:
                _ensure_logging()
        return self._enabled

    def __post_init__(self) -> None:
        self._origin = time.perf_counter()

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
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

    def finish(self, label: str = "startup total") -> None:
        if not self.enabled:
            return
        total_ms = (time.perf_counter() - self._origin) * 1000
        logger.info("%s %.0fms (%d phases)", label, total_ms, len(self._records))
        if len(self._records) > 1:
            ranked = sorted(self._records, key=lambda item: item[1], reverse=True)
            parts = ", ".join(f"{name} {ms:.0f}ms" for name, ms in ranked[:5])
            logger.info("startup slowest: %s", parts)


profiler = StartupProfiler()
