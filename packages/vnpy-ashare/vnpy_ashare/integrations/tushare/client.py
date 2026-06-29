"""Tushare Pro 客户端。"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from typing import Any

import tushare as ts
from dotenv import load_dotenv
from vnpy.trader.setting import SETTINGS

from vnpy_ashare.integrations.tushare.rate_limit import is_transient_network_error, transient_retry_delay
from vnpy_common.paths import ENV_FILE

_DEFAULT_API_BASE = "https://api.tushare.pro/dataapi"
_MAX_TRANSIENT_RETRIES = 3


class TushareNotConfiguredError(RuntimeError):
    """未配置 TUSHARE_TOKEN。"""


def resolve_tushare_api_base() -> str:
    """Tushare HTTP API 根路径（不含接口名，如 daily）。"""
    raw = os.getenv("TUSHARE_API_URL", _DEFAULT_API_BASE).strip().rstrip("/")
    return raw or _DEFAULT_API_BASE


def _apply_api_base(pro: Any) -> None:
    pro._DataApi__http_url = resolve_tushare_api_base()


def _wrap_query_with_transient_retry(pro: Any) -> Any:
    original_query: Callable[..., Any] = pro.query

    def query_with_retry(api_name: str, fields: str = "", **kwargs: Any) -> Any:
        last_exc: Exception | None = None
        for attempt in range(_MAX_TRANSIENT_RETRIES):
            try:
                return original_query(api_name, fields=fields, **kwargs)
            except Exception as ex:
                last_exc = ex
                if is_transient_network_error(ex) and attempt + 1 < _MAX_TRANSIENT_RETRIES:
                    time.sleep(transient_retry_delay(attempt))
                    continue
                raise
        assert last_exc is not None
        raise last_exc

    pro.query = query_with_retry
    return pro


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
    pro = ts.pro_api(token)
    _apply_api_base(pro)
    return _wrap_query_with_transient_retry(pro)
