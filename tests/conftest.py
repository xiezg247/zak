"""pytest 入口：统一项目根路径与 workspace 包导入。"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

import tests._bootstrap  # noqa: F401

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


@pytest.fixture(scope="session", autouse=True)
def _install_ashare_bridges() -> None:
    try:
        from vnpy_ashare.app.bootstrap import install_shared_bridges

        install_shared_bridges()
    except ImportError:
        pass


@pytest.fixture
def pg_storage():
    """绑定 .env 中的 DATABASE_URL 供存储层集成测试。"""
    from vnpy_common.storage.config import force_database_url, reset_storage_config

    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        pytest.skip("需要 DATABASE_URL 环境变量")
    force_database_url(url)
    yield url
    reset_storage_config()
