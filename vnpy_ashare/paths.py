"""项目路径统一入口。"""

from __future__ import annotations

from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PROJECT_ROOT / "data"
BACKUP_DIR = DATA_DIR / "backup"
ENV_FILE = PROJECT_ROOT / ".env"
VNTRADER_DIR = Path.home() / ".vntrader"
APP_DB_PATH = VNTRADER_DIR / "vnpy_zak.db"
