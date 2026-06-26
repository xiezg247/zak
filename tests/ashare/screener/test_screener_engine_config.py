"""选股引擎配置。"""

from __future__ import annotations

import pytest

from vnpy_ashare.screener.engine.config import polars_available, polars_engine_enabled, screener_engine


def test_screener_engine_defaults_to_python(monkeypatch):
    monkeypatch.delenv("ZAK_SCREENER_ENGINE", raising=False)
    assert screener_engine() == "python"
    assert polars_engine_enabled() is False


def test_screener_engine_polars_flag(monkeypatch):
    monkeypatch.setenv("ZAK_SCREENER_ENGINE", "polars")
    assert screener_engine() == "polars"
    assert polars_engine_enabled() is True


def test_polars_available():
    pytest.importorskip("polars")
    assert polars_available() is True
