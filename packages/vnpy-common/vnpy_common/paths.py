"""项目路径统一入口。"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
VNTRADER_DIR = Path.home() / ".vntrader"
APP_ID = "zak"
QSETTINGS_ORG = APP_ID
SETTINGS_APP = "ZakTerminal"

_settings_loader: Callable[[], dict] | None = None


def register_settings_loader(loader: Callable[[], dict]) -> None:
    global _settings_loader
    _settings_loader = loader


def resolve_project_root() -> Path:
    """解析 zak 仓库根目录（含 skills/、run.py）。"""
    env_root = os.environ.get("ZAK_PROJECT_ROOT", "").strip()
    if env_root:
        return Path(env_root).resolve()
    for parent in Path.cwd().resolve().parents:
        if (parent / "run.py").is_file() and (parent / "skills").is_dir():
            return parent
    for parent in PACKAGE_ROOT.parents:
        if (parent / "run.py").is_file() and (parent / "skills").is_dir():
            return parent
    return Path.cwd().resolve()


PROJECT_ROOT = resolve_project_root()
DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = DATA_DIR / "backup"
ENV_FILE = PROJECT_ROOT / ".env"
