"""vt_setting.json 构建与读写（GUI 与 init_config 共用）。"""

from __future__ import annotations

import json
from copy import copy
from pathlib import Path

from dotenv import load_dotenv
from vnpy.trader.setting import SETTING_FILENAME, SETTINGS
from vnpy.trader.utility import load_json, save_json

from vnpy_ashare.config_bridge import (
    build_vt_settings_from_env_file,
    sqlite_database_settings,
)
from vnpy_ashare.paths import ENV_FILE, VNTRADER_DIR
from vnpy_ashare.ui.fonts import default_font_family

SETTING_FILE = VNTRADER_DIR / SETTING_FILENAME


def default_vt_settings() -> dict:
    """vt_setting.json 默认值（不含 .env 与已持久化覆盖）。"""
    return {
        "font.family": default_font_family(),
        "font.size": 12,
        "log.active": True,
        "log.level": "INFO",
        **sqlite_database_settings(),
        "database.http_port": 9000,
        "datafeed.name": "tickflow",
        "datafeed.username": "api_key",
        "datafeed.password": "",
    }


def build_vt_settings() -> dict:
    """根据 .env 生成 VeighNa 全局配置。"""
    load_dotenv(ENV_FILE)
    return build_vt_settings_from_env_file(ENV_FILE)


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
