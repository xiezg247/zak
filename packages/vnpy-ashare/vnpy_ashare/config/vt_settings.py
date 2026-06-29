"""vt_setting.json 构建与读写（GUI 与启动入口共用）。"""

from __future__ import annotations

import json
from copy import copy
from pathlib import Path

from dotenv import load_dotenv
from vnpy.trader.setting import SETTING_FILENAME, SETTINGS
from vnpy.trader.utility import load_json, save_json

from vnpy_ashare.config.bridge import (
    build_vt_settings_from_env_file,
    meta_database_settings,
    postgres_database_settings,
)
from vnpy_ashare.config.fonts import default_font_family
from vnpy_common.paths import ENV_FILE, VNTRADER_DIR

SETTING_FILE = VNTRADER_DIR / SETTING_FILENAME


def default_vt_settings() -> dict:
    """vt_setting.json 默认值（不含 .env 与已持久化覆盖）。"""
    return {
        "font.family": default_font_family(),
        "font.size": 12,
        "log.active": True,
        "log.level": "INFO",
        **postgres_database_settings(),
        **meta_database_settings(),
        "datafeed.name": "tickflow",
        "datafeed.username": "api_key",
        "datafeed.password": "",
    }


def build_vt_settings() -> dict:
    """根据 .env 生成 VeighNa 全局配置。"""
    load_dotenv(ENV_FILE)
    from vnpy_common.perf_profile import apply_perf_profile_from_env

    apply_perf_profile_from_env()
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


def vt_settings_needs_env_bootstrap(setting_file: Path = SETTING_FILE) -> bool:
    """vt_setting.json 缺失、为空、仅 {} 或非法 JSON 时需从 .env 重建。"""
    if not setting_file.is_file():
        return True
    text = setting_file.read_text(encoding="utf-8").strip()
    if not text:
        return True
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return True
    return not isinstance(data, dict) or not data


def ensure_vt_settings_from_env() -> bool:
    """启动时若 vt_setting.json 无效或为空，则从 .env 生成。"""
    if not vt_settings_needs_env_bootstrap(SETTING_FILE):
        return False
    sync_vt_settings_from_env(backup=False)
    return True


def reload_vnpy_settings() -> None:
    """将 vt_setting.json 合并进 vnpy 全局 SETTINGS（生成新文件后调用）。"""

    SETTINGS.update(load_json(SETTING_FILENAME))
