#!/usr/bin/env python3
"""根据 .env 生成 VeighNa 全局配置文件"""

from __future__ import annotations

from vnpy_ashare.config import write_backtest_defaults
from vnpy_ashare.vt_settings import SETTING_FILE, build_vt_settings, sync_vt_settings_from_env


def main() -> None:
    settings = build_vt_settings()
    sync_vt_settings_from_env(backup=True)
    backtest_file = write_backtest_defaults()
    print(f"A股回测默认参数: {backtest_file}")

    print(f"配置已写入: {SETTING_FILE}")
    print(f"当前数据库: {settings['database.name']}")
    if settings["database.name"] == "postgresql":
        print(f"PostgreSQL: {settings['database.host']}:{settings['database.port']}")
        print("提示: 需已安装 uv sync --extra postgresql 并启动 scripts/start_postgresql.sh")
    print(f"当前数据服务: {settings['datafeed.name']}")
    if settings["datafeed.name"] == "tickflow":
        has_key = bool(settings.get("datafeed.password"))
        print(f"TickFlow: {'Pro（已配置 API Key）' if has_key else '免费日K'}")
    if settings["datafeed.name"] == "tushare":
        has_token = bool(settings.get("datafeed.password"))
        print(f"Tushare: {'已配置 Token' if has_token else '未配置 Token'}")


if __name__ == "__main__":
    main()
