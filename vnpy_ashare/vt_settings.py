"""vt_setting.json 构建与读写（GUI 与 init_config 共用）。"""

from __future__ import annotations

import json
import os
from copy import copy
from pathlib import Path

from dotenv import load_dotenv
from vnpy.trader.setting import SETTING_FILENAME, SETTINGS
from vnpy.trader.utility import load_json, save_json

from vnpy_ashare.paths import ENV_FILE, VNTRADER_DIR
from vnpy_ashare.ui.fonts import default_font_family

SETTING_FILE = VNTRADER_DIR / SETTING_FILENAME


def _sqlite_database_settings() -> dict:
    return {
        "database.name": "sqlite",
        "database.database": "database.db",
        "database.host": "",
        "database.port": 0,
        "database.user": "",
        "database.password": "",
    }


def _questdb_database_settings() -> dict:
    return {
        "database.name": "questdb",
        "database.host": os.getenv("QUESTDB_HOST", "localhost"),
        "database.port": int(os.getenv("QUESTDB_PORT", "8812")),
        "database.http_port": int(os.getenv("QUESTDB_HTTP_PORT", "9000")),
        "database.user": os.getenv("QUESTDB_USER", "admin"),
        "database.password": os.getenv("QUESTDB_PASSWORD", "quest"),
        "database.database": os.getenv("QUESTDB_DATABASE", "qdb"),
    }


def _database_settings() -> dict:
    name = os.getenv("DATABASE_NAME", "sqlite").strip().lower()
    if name == "questdb":
        return _questdb_database_settings()
    return _sqlite_database_settings()


def _base_settings() -> dict:
    return {
        "font.family": default_font_family(),
        "font.size": 12,
        "log.active": True,
        "log.level": "INFO",
        **_database_settings(),
    }


def default_vt_settings() -> dict:
    """vt_setting.json 默认值（不含 .env 与已持久化覆盖）。"""
    return {
        "font.family": default_font_family(),
        "font.size": 12,
        "log.active": True,
        "log.level": "INFO",
        **_sqlite_database_settings(),
        "database.http_port": 9000,
        "datafeed.name": "tickflow",
        "datafeed.username": "api_key",
        "datafeed.password": "",
    }


def build_vt_settings() -> dict:
    """根据 .env 生成 VeighNa 全局配置。"""
    load_dotenv(ENV_FILE)

    datafeed_name = os.getenv("DATAFEED_NAME", "tickflow").lower()
    tushare_token = os.getenv("TUSHARE_TOKEN", "")
    tickflow_api_key = os.getenv("TICKFLOW_API_KEY", "")

    if datafeed_name == "tushare":
        return {
            **_base_settings(),
            "datafeed.name": "tushare",
            "datafeed.username": "token",
            "datafeed.password": tushare_token,
        }

    return {
        **_base_settings(),
        "datafeed.name": "tickflow",
        "datafeed.username": "api_key",
        "datafeed.password": tickflow_api_key,
    }


def load_runtime_settings() -> dict:
    """读取当前运行时配置（默认项 + vt_setting.json）。"""
    settings = copy(SETTINGS)
    settings.update(load_json(SETTING_FILENAME))
    return settings


def save_runtime_settings(updates: dict) -> Path:
    """合并写入 vt_setting.json，保留未编辑的键。"""
    current = load_runtime_settings()
    current.update(updates)
    save_json(SETTING_FILENAME, current)
    return SETTING_FILE


def sync_vt_settings_from_env(*, backup: bool = True) -> Path:
    """用 .env 重建 vt_setting.json。"""
    settings = build_vt_settings()
    VNTRADER_DIR.mkdir(parents=True, exist_ok=True)

    if backup and SETTING_FILE.exists():
        backup_path = SETTING_FILE.with_suffix(".json.bak")
        SETTING_FILE.rename(backup_path)

    with SETTING_FILE.open("w", encoding="utf-8") as handle:
        json.dump(settings, handle, indent=4, ensure_ascii=False)

    return SETTING_FILE
