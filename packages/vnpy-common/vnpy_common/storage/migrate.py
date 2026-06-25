"""Alembic 程序化升级。"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from vnpy_common.paths import PROJECT_ROOT


def alembic_config() -> Config:
    ini_path = PROJECT_ROOT / "alembic.ini"
    cfg = Config(str(ini_path))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    return cfg


def upgrade_head(revision: str = "head") -> None:
    command.upgrade(alembic_config(), revision)
