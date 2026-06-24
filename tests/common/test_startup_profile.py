"""启动 profiling 工具测试。"""

from __future__ import annotations

import time

from vnpy_common.startup_profile import StartupProfiler, startup_profile_enabled


def _use_env_file(monkeypatch, tmp_path, content: str = "") -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(content, encoding="utf-8")
    monkeypatch.setattr("vnpy_common.startup_profile._env_loaded", False)
    monkeypatch.setattr("vnpy_common.paths.ENV_FILE", env_file)


def test_startup_profile_disabled_by_default(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZAK_STARTUP_PROFILE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    assert startup_profile_enabled() is False


def test_startup_profile_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZAK_STARTUP_PROFILE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    monkeypatch.setenv("ZAK_STARTUP_PROFILE", "1")
    assert startup_profile_enabled() is True


def test_profiler_records_phases_when_enabled(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZAK_STARTUP_PROFILE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    monkeypatch.setenv("ZAK_STARTUP_PROFILE", "1")
    profiler = StartupProfiler()
    with profiler.phase("a"):
        time.sleep(0.01)
    with profiler.phase("b"):
        pass
    assert len(profiler._records) == 2
    assert profiler._records[0][0] == "a"
    assert profiler._records[0][1] >= 5


def test_profiler_reads_env_file(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZAK_STARTUP_PROFILE", raising=False)
    _use_env_file(monkeypatch, tmp_path, "ZAK_STARTUP_PROFILE=1\n")
    assert startup_profile_enabled() is True


def test_profiler_skips_records_when_disabled(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("ZAK_STARTUP_PROFILE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    profiler = StartupProfiler()
    with profiler.phase("a"):
        time.sleep(0.001)
    assert profiler._records == []


def test_profiler_logs_to_stdout_when_enabled(monkeypatch, tmp_path, capfd) -> None:
    monkeypatch.delenv("ZAK_STARTUP_PROFILE", raising=False)
    _use_env_file(monkeypatch, tmp_path)
    monkeypatch.setenv("ZAK_STARTUP_PROFILE", "1")
    from vnpy_common.startup_profile import logger

    logger.handlers.clear()
    profiler = StartupProfiler()
    with profiler.phase("phase_x"):
        pass
    profiler.finish("done")
    out, _err = capfd.readouterr()
    assert "phase_x" in out
    assert "done" in out
