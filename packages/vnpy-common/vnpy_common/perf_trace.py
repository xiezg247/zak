"""运行时热路径耗时 tracing（``ZAK_PERF_TRACE=1`` 启用）。"""

from __future__ import annotations

import logging
import os
import statistics
import sys
import time
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

logger = logging.getLogger("perf")

_TRUTHY = frozenset({"1", "true", "yes", "on"})

_env_loaded = False


@dataclass(frozen=True)
class SpanAggregate:
    """同名 span 多次采样的聚合统计。"""

    name: str
    count: int
    total_ms: float
    p50_ms: float
    p95_ms: float
    max_ms: float


def aggregate_span_records(records: list[tuple[str, float]]) -> list[SpanAggregate]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for name, elapsed_ms in records:
        buckets[name].append(elapsed_ms)

    aggregates: list[SpanAggregate] = []
    for name, values in buckets.items():
        sorted_vals = sorted(values)
        count = len(sorted_vals)
        aggregates.append(
            SpanAggregate(
                name=name,
                count=count,
                total_ms=sum(sorted_vals),
                p50_ms=statistics.median(sorted_vals),
                p95_ms=sorted_vals[max(0, int(count * 0.95) - 1)],
                max_ms=sorted_vals[-1],
            )
        )
    return sorted(aggregates, key=lambda item: item.p95_ms, reverse=True)


def format_baseline_report(
    bench_rows: list[dict[str, float]],
    span_aggregates: list[SpanAggregate],
    *,
    top_n: int = 5,
    title: str = "zak 性能基线报告",
) -> str:
    lines = [title, "=" * len(title), ""]
    if bench_rows:
        lines.append("## 基准项（bench）")
        lines.append(f"{'name':32s}  {'p50':>8s}  {'p95':>8s}  {'max':>8s}  n")
        for row in bench_rows:
            lines.append(
                f"{row['name']:32s}  {row['p50_ms']:8.1f}  {row['p95_ms']:8.1f}  "
                f"{row['max_ms']:8.1f}  {int(row.get('result_size', 0))}"
            )
        lines.append("")
    if span_aggregates:
        lines.append(f"## 运行时 span Top {top_n}（P95 降序）")
        lines.append(f"{'span':40s}  {'count':>5s}  {'p50':>8s}  {'p95':>8s}  {'max':>8s}")
        for item in span_aggregates[:top_n]:
            lines.append(
                f"{item.name:40s}  {item.count:5d}  {item.p50_ms:8.1f}  {item.p95_ms:8.1f}  {item.max_ms:8.1f}"
            )
        lines.append("")
        lines.append("## 热点（按 P95 × count 加权）")
        weighted = sorted(span_aggregates, key=lambda item: item.p95_ms * item.count, reverse=True)
        for index, item in enumerate(weighted[:top_n], start=1):
            lines.append(f"{index}. {item.name} — p95 {item.p95_ms:.0f}ms × {item.count} = {item.p95_ms * item.count:.0f}ms·count")
    return "\n".join(lines)


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
        ranked = self.aggregates(top_n=top_n)
        if ranked:
            parts = ", ".join(f"{item.name} {item.p95_ms:.0f}ms" for item in ranked[:top_n])
            logger.info("perf slowest (p95): %s", parts)

    def aggregates(self, *, top_n: int | None = None) -> list[SpanAggregate]:
        ranked = aggregate_span_records(self._records)
        if top_n is None:
            return ranked
        return ranked[:top_n]

    def baseline_report(
        self,
        bench_rows: list[dict[str, float]] | None = None,
        *,
        top_n: int = 5,
        title: str = "zak 性能基线报告",
    ) -> str:
        return format_baseline_report(
            bench_rows or [],
            self.aggregates(),
            top_n=top_n,
            title=title,
        )

    def reset(self) -> None:
        self._records.clear()


tracer = PerfTracer()
