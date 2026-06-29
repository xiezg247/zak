"""Redis 行情编码：JSON blob（``ZAK_REDIS_QUOTE_BLOB=1``）为主路径；HASH 短 field key 在 BLOB 开启时默认启用。"""

from __future__ import annotations

import json
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
    raw = os.getenv("ZAK_REDIS_QUOTE_COMPACT", "").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    if raw in _TRUTHY:
        return True
    return quote_blob_enabled()


def quote_blob_enabled() -> bool:
    return os.getenv("ZAK_REDIS_QUOTE_BLOB", "").strip().lower() in _TRUTHY


def _json_dumps(data: dict[str, str]) -> str:
    try:
        import orjson

        return orjson.dumps(data).decode("utf-8")
    except ImportError:
        return json.dumps(data, separators=(",", ":"), ensure_ascii=False)


def _json_loads(raw: str) -> dict[str, str]:
    try:
        import orjson

        loaded = orjson.loads(raw)
    except ImportError:
        loaded = json.loads(raw)
    if not isinstance(loaded, dict):
        return {}
    return {str(key): str(value) for key, value in loaded.items()}


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


_ENRICH_FIELD_NAMES: tuple[str, ...] = (
    "turnover_rate",
    "volume_ratio",
    "net_mf_amount",
    "change_speed_5m",
    "limit_times",
)


def encode_enrich_hash(quote: QuoteSnapshot) -> dict[str, str]:
    """异步 enrich Job 仅 PATCH Tushare / 榜相关字段。"""
    raw = quote.to_redis_hash()
    mapping = {key: raw[key] for key in _ENRICH_FIELD_NAMES if key in raw}
    if not quote_compact_enabled():
        return mapping
    return {QUOTE_FIELD_TO_SHORT.get(key, key): value for key, value in mapping.items()}


def encode_quote_blob(quote: QuoteSnapshot) -> str:
    """单次 SET 的 JSON blob（与 HASH 字段集一致，可配合 MGET 批量读）。"""
    return _json_dumps(encode_quote_hash(quote))


def decode_quote_blob(raw: str | bytes | None) -> QuoteSnapshot | None:
    if not raw:
        return None
    text = raw.decode("utf-8") if isinstance(raw, bytes) else str(raw)
    if not text.strip():
        return None
    try:
        data = normalize_redis_hash(_json_loads(text))
    except (json.JSONDecodeError, TypeError, ValueError):
        return None
    return QuoteSnapshot.from_redis_hash(data)
