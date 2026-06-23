"""B 站 HTTP 客户端：Cookie 鉴权与 WBI 签名。"""

from __future__ import annotations

import hashlib
import os
import re
import time
from functools import reduce
from typing import Any
from urllib.parse import urlencode

import requests

_API_BASE = "https://api.bilibili.com"
_DEFAULT_TIMEOUT = 20
_WBI_MIXIN_KEY_TABLE = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]


class BilibiliApiError(Exception):
    def __init__(self, message: str, *, code: int | None = None) -> None:
        super().__init__(message)
        self.code = code


class BilibiliClient:
    def __init__(self, *, cookies: str | None = None, session: requests.Session | None = None) -> None:
        self._session = session or requests.Session()
        self._cookies = (cookies if cookies is not None else os.environ.get("BILIBILI_COOKIES", "")).strip()
        self._img_key = ""
        self._sub_key = ""
        self._wbi_refreshed_at = 0.0

    @property
    def cookies_configured(self) -> bool:
        return bool(self._cookies)

    def _headers(self) -> dict[str, str]:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.bilibili.com",
        }
        if self._cookies:
            headers["Cookie"] = self._cookies
        return headers

    def _ensure_wbi_keys(self) -> None:
        if self._img_key and self._sub_key and time.time() - self._wbi_refreshed_at < 3600:
            return
        payload = self._get_json("/x/web-interface/nav", signed=False)
        wbi_img = str(payload.get("wbi_img", {}).get("img_url", ""))
        wbi_sub = str(payload.get("wbi_img", {}).get("sub_url", ""))
        self._img_key = _extract_filename_key(wbi_img)
        self._sub_key = _extract_filename_key(wbi_sub)
        self._wbi_refreshed_at = time.time()

    def _sign_params(self, params: dict[str, Any]) -> dict[str, Any]:
        self._ensure_wbi_keys()
        signed = dict(params)
        signed["wts"] = int(time.time())
        signed = dict(sorted(signed.items()))
        filtered = {k: _filter_wbi_value(v) for k, v in signed.items()}
        query = urlencode(filtered)
        mixin_key = _mixin_key(self._img_key + self._sub_key)
        signed["w_rid"] = hashlib.md5(f"{query}{mixin_key}".encode()).hexdigest()
        return signed

    def _get_json(self, path: str, *, params: dict[str, Any] | None = None, signed: bool = True) -> dict[str, Any]:
        query = dict(params or {})
        if signed:
            query = self._sign_params(query)
        url = f"{_API_BASE}{path}"
        try:
            response = self._session.get(
                url,
                params=query,
                headers=self._headers(),
                timeout=_DEFAULT_TIMEOUT,
            )
            response.raise_for_status()
            body = response.json()
        except requests.RequestException as ex:
            raise BilibiliApiError(f"请求失败：{ex}") from ex
        except ValueError as ex:
            raise BilibiliApiError("响应不是合法 JSON") from ex

        code = int(body.get("code", -1))
        if code != 0:
            message = str(body.get("message") or body.get("msg") or "未知错误")
            raise BilibiliApiError(message, code=code)
        data = body.get("data")
        if not isinstance(data, dict):
            return {}
        return data


def _extract_filename_key(url: str) -> str:
    name = url.rsplit("/", 1)[-1]
    return name.split(".", 1)[0]


def _mixin_key(raw: str) -> str:
    if len(raw) < max(_WBI_MIXIN_KEY_TABLE) + 1:
        return raw[:32]
    return reduce(lambda acc, index: acc + raw[index], _WBI_MIXIN_KEY_TABLE, "")[:32]


def _filter_wbi_value(value: Any) -> str:
    text = str(value)
    return re.sub(r"[!'()*]", "", text)
