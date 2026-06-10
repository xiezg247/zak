"""项目路径统一入口。"""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = DATA_DIR / "backup"
ENV_FILE = PROJECT_ROOT / ".env"
VNTRADER_DIR = Path.home() / ".vntrader"
APP_ID = "zak"
# Qt QSettings 组织名（macOS ~/Library/Preferences、Windows 注册表等）
QSETTINGS_ORG = APP_ID

META_APP_SETTING_KEY = "database.meta.app"
META_CHAT_SETTING_KEY = "database.meta.chat"
DEFAULT_META_APP_FILE = f"{APP_ID}.db"
DEFAULT_META_CHAT_FILE = "llm_chat.db"


def _runtime_settings(settings: dict | None) -> dict:
    if settings is not None:
        return settings
    from vnpy_ashare.vt_settings import load_runtime_settings

    return load_runtime_settings()


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


# 兼容旧 import；新代码请用 get_app_db_path()
APP_DB_PATH = VNTRADER_DIR / DEFAULT_META_APP_FILE
