"""pytest 入口：统一项目根路径与 workspace 包导入。"""

from __future__ import annotations

import pytest

import tests._bootstrap  # noqa: F401


@pytest.fixture(scope="session", autouse=True)
def _install_ashare_bridges() -> None:
    try:
        from vnpy_ashare.app.bootstrap import install_shared_bridges

        install_shared_bridges()
    except ImportError:
        pass
