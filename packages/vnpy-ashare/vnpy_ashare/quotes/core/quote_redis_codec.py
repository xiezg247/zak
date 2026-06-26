"""Redis 行情 HASH 紧凑 field key（``ZAK_REDIS_QUOTE_COMPACT=1``）。"""

from __future__ import annotations

import os

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot

_TRUTHY = frozenset({"1", "true", "yes", "on"})

# 长 field → 短 field；读写均兼容两种格式
QUOTE_FIELD_TO_SHORT: dict[str, str] = {
    "symbol": "s",
    "name": "n",
    "last_price": "lp",
    "prev_close": "pc",
    "open_price": "op",
    "high_price": "hi",
    "low_price": "lo",
    "change_amount": "ca",
    "change_pct": "cp",
    "turnover_rate": "tr",
    "volume": "v",
    "amount": "a",
    "amplitude": "amp",
    "volume_ratio": "vr",
    "net_mf_amount": "nmf",
    "change_speed_5m": "cs5",
    "limit_times": "lt",
    "trade_time": "tt",
}

SHORT_TO_QUOTE_FIELD: dict[str, str] = {short: long for long, short in QUOTE_FIELD_TO_SHORT.items()}


def quote_compact_enabled() -> bool:
    return os.getenv("ZAK_REDIS_QUOTE_COMPACT", "").strip().lower() in _TRUTHY


def normalize_redis_hash(data: dict[str, str]) -> dict[str, str]:
    """短 key → 长 key，供 ``QuoteSnapshot.from_redis_hash`` 使用。"""
    if not data:
        return data
    if not any(key in SHORT_TO_QUOTE_FIELD for key in data):
        return data
    normalized: dict[str, str] = {}
    for key, value in data.items():
        long_key = SHORT_TO_QUOTE_FIELD.get(key, key)
        if long_key in normalized and long_key != key:
            continue
        normalized[long_key] = value
    return normalized


def encode_quote_hash(quote: QuoteSnapshot) -> dict[str, str]:
    """写入 Redis 的 HASH mapping。"""
    raw = quote.to_redis_hash()
    if not quote_compact_enabled():
        return raw
    return {QUOTE_FIELD_TO_SHORT.get(key, key): value for key, value in raw.items()}
