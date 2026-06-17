"""Tushare Pro 客户端。"""

from __future__ import annotations

import os

import tushare as ts
from dotenv import load_dotenv
from vnpy.trader.setting import SETTINGS

from vnpy_common.paths import ENV_FILE


class TushareNotConfiguredError(RuntimeError):
    """未配置 TUSHARE_TOKEN。"""


def get_tushare_pro():

    load_dotenv(ENV_FILE)
    token = os.getenv("TUSHARE_TOKEN") or os.getenv("TS_TOKEN")
    if not token:
        try:
            token = SETTINGS.get("datafeed.password") or ""
        except Exception:
            token = ""
    if not token:
        raise TushareNotConfiguredError("未配置 TUSHARE_TOKEN。请在 .env 中设置后重试。")

    ts.set_token(token)
    return ts.pro_api(token)
