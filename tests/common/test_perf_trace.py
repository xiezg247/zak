"""运行时 perf tracing 工具测试。"""

from __future__ import annotations

import time

from vnpy_common.perf_trace import PerfTracer, perf_trace_enabled


def _use_env_file(monkeypatch, tmp_path, content: str = "") -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(content, encoding="utf-8")
    monkeypatch.setattr("vnpy_common.perf_trace._env_loaded", False)
    monkeypatch.setattr("vnpy_common.paths.ENV_FILE", env_file)


def test_perf_trace_disabled_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZAK_PERF_TRACE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    assert perf_trace_enabled() is False


def test_perf_trace_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZAK_PERF_TRACE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    monkeypatch.setenv("ZAK_PERF_TRACE", "1")
    assert perf_trace_enabled() is True


def test_tracer_records_spans_when_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZAK_PERF_TRACE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    monkeypatch.setenv("ZAK_PERF_TRACE", "1")
    tracer = PerfTracer()
    with tracer.trace("a"):
        time.sleep(0.01)
    with tracer.trace("b"):
        pass
    assert len(tracer._records) == 2
    assert tracer._records[0][0] == "a"
    assert tracer._records[0][1] >= 5


def test_tracer_skips_when_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZAK_PERF_TRACE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    tracer = PerfTracer()
    with tracer.trace("a"):
        time.sleep(0.001)
    assert tracer._records == []


def test_tracer_logs_to_stdout_when_enabled(monkeypatch, tmp_path, capfd) -> None:
    monkeypatch.delenv("ZAK_PERF_TRACE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    monkeypatch.setenv("ZAK_PERF_TRACE", "1")
    from vnpy_common.perf_trace import logger

    logger.handlers.clear()
    tracer = PerfTracer()
    with tracer.trace("span_x"):
        pass
    tracer.summary("done")
    out, _err = capfd.readouterr()
    assert "span_x" in out
    assert "done" in out


def test_aggregate_span_records(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZAK_PERF_TRACE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    from vnpy_common.perf_trace import SpanAggregate, aggregate_span_records, format_baseline_report

    records = [("a", 10.0), ("a", 20.0), ("b", 5.0)]
    ranked = aggregate_span_records(records)
    assert isinstance(ranked[0], SpanAggregate)
    assert ranked[0].name == "a"
    assert ranked[0].p50_ms == 15.0
    report = format_baseline_report(
        [{"name": "x", "p50_ms": 1.0, "p95_ms": 2.0, "max_ms": 3.0, "result_size": 1.0}],
        ranked,
        top_n=2,
    )
    assert "基准项" in report
    assert "热点" in report
