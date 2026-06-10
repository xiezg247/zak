"""Tushare Pro 客户端（选股基本面数据）。"""

from __future__ import annotations

import os


class TushareNotConfiguredError(RuntimeError):
    """未配置 TUSHARE_TOKEN。"""


def get_tushare_pro():
    from dotenv import load_dotenv

    from vnpy_common.paths import ENV_FILE

    load_dotenv(ENV_FILE)
    token = os.getenv("TUSHARE_TOKEN") or os.getenv("TS_TOKEN")
    if not token:
        try:
            from vnpy.trader.setting import SETTINGS

            token = SETTINGS.get("datafeed.password") or ""
        except Exception:
            token = ""
    if not token:
        raise TushareNotConfiguredError("未配置 TUSHARE_TOKEN。请在 .env 中设置后重试。")
    import tushare as ts

    ts.set_token(token)
    return ts.pro_api(token)
