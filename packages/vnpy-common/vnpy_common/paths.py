"""项目路径统一入口。"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
VNTRADER_DIR = Path.home() / ".vntrader"
APP_ID = "zak"
QSETTINGS_ORG = APP_ID

META_APP_SETTING_KEY = "database.meta.app"
META_CHAT_SETTING_KEY = "database.meta.chat"
DEFAULT_META_APP_FILE = f"{APP_ID}.db"
DEFAULT_META_CHAT_FILE = "llm_chat.db"

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


def _runtime_settings(settings: dict | None) -> dict:
    if settings is not None:
        return settings
    if _settings_loader is not None:
        return _settings_loader()
    return {}


def meta_db_filenames(settings: dict | None = None) -> tuple[str, str]:
    """元数据 SQLite 相对路径（相对 ~/.vntrader/）。"""
    runtime = _runtime_settings(settings)
    app_file = str(runtime.get(META_APP_SETTING_KEY, DEFAULT_META_APP_FILE)).strip() or DEFAULT_META_APP_FILE
    chat_file = str(runtime.get(META_CHAT_SETTING_KEY, DEFAULT_META_CHAT_FILE)).strip() or DEFAULT_META_CHAT_FILE
    return app_file, chat_file


def get_app_db_path(settings: dict | None = None) -> Path:
    """业务元数据 SQLite 绝对路径。"""
    app_file, _ = meta_db_filenames(settings)
    return VNTRADER_DIR / app_file


def get_chat_db_path(settings: dict | None = None) -> Path:
    """AI 对话 SQLite 绝对路径。"""
    _, chat_file = meta_db_filenames(settings)
    return VNTRADER_DIR / chat_file


APP_DB_PATH = VNTRADER_DIR / DEFAULT_META_APP_FILE
