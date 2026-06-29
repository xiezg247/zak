"""Polars 为选股引擎必选依赖。"""

from __future__ import annotations

import importlib

import polars as pl


def test_polars_core_dependency() -> None:
    assert pl.__version__


def test_screener_engine_config_exports_polars() -> None:
    config = importlib.import_module("vnpy_ashare.screener.engine.config")
    assert config.pl is pl
