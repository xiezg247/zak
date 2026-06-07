#!/usr/bin/env python3
"""根据 .env 生成 VeighNa 全局配置文件"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from vnpy_ashare.config import write_backtest_defaults
from vnpy_ashare.paths import ENV_FILE, VNTRADER_DIR
from vnpy_ashare.ui.fonts import default_font_family

SETTING_FILE = VNTRADER_DIR / "vt_setting.json"


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


def build_settings() -> dict:
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


def main() -> None:
    settings = build_settings()
    VNTRADER_DIR.mkdir(parents=True, exist_ok=True)

    if SETTING_FILE.exists():
        backup = SETTING_FILE.with_suffix(".json.bak")
        SETTING_FILE.rename(backup)
        print(f"已备份原配置到: {backup}")

    with SETTING_FILE.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

    backtest_file = write_backtest_defaults()
    print(f"A股回测默认参数: {backtest_file}")

    print(f"配置已写入: {SETTING_FILE}")
    print(f"当前数据库: {settings['database.name']}")
    if settings["database.name"] == "questdb":
        print(
            f"QuestDB: {settings['database.host']}:{settings['database.port']} "
            f"(http {settings['database.http_port']})"
        )
        print("提示: 需已安装 uv sync --extra questdb 并启动 scripts/start_questdb.sh")
    print(f"当前数据服务: {settings['datafeed.name']}")
    if settings["datafeed.name"] == "tickflow":
        has_key = bool(settings.get("datafeed.password"))
        print(f"TickFlow: {'Pro（已配置 API Key）' if has_key else '免费日K'}")
    if settings["datafeed.name"] == "tushare":
        has_token = bool(settings.get("datafeed.password"))
        print(f"Tushare: {'已配置 Token' if has_token else '未配置 Token'}")


if __name__ == "__main__":
    main()
