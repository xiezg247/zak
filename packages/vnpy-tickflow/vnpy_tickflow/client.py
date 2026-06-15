"""TickFlow 客户端。"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from tickflow import TickFlow

from vnpy_common.paths import ENV_FILE


def resolve_tickflow_api_key(*, settings_key: str = "") -> str:
    load_dotenv(ENV_FILE, override=False)
    if settings_key:
        return settings_key.strip()
    env_key = os.getenv("TICKFLOW_API_KEY", "").strip()
    if env_key:
        return env_key
    try:
        from vnpy.trader.setting import SETTINGS

        if str(SETTINGS.get("datafeed.name", "")).strip().lower() == "tickflow":
            vt_key = str(SETTINGS.get("datafeed.password", "")).strip()
            if vt_key:
                return vt_key
    except Exception:
        pass
    return ""


def get_tickflow_client(*, api_key: str | None = None) -> TickFlow:
    """创建 TickFlow 客户端；无 API Key 时使用免费日 K 服务。"""
    key = resolve_tickflow_api_key(settings_key=api_key or "")
    if key:
        return TickFlow(api_key=key)
    return TickFlow.free()


def is_free_mode(*, api_key: str | None = None) -> bool:
    return not resolve_tickflow_api_key(settings_key=api_key or "")
