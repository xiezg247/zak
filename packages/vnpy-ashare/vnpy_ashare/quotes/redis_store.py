"""Redis 行情存储：快照 HASH + 涨幅榜 ZSET。"""

from __future__ import annotations

import os
from datetime import datetime

from dotenv import load_dotenv

from vnpy_ashare.domain.quote_time import normalize_datetime_text
from vnpy_ashare.quotes.snapshot import QuoteSnapshot
from vnpy_common.paths import ENV_FILE

KEY_PREFIX = "zak"
QUOTE_KEY_FMT = f"{KEY_PREFIX}:quote:{{symbol}}"
RANK_CHANGE_PCT_KEY = f"{KEY_PREFIX}:rank:change_pct"
META_UPDATED_AT_KEY = f"{KEY_PREFIX}:meta:updated_at"
META_QUOTE_COUNT_KEY = f"{KEY_PREFIX}:meta:quote_count"


def quote_key(tf_symbol: str) -> str:
    return QUOTE_KEY_FMT.format(symbol=tf_symbol)


def create_redis_client():
    load_dotenv(ENV_FILE)
    url = os.getenv("REDIS_URL", "").strip() or "redis://127.0.0.1:6379/0"
    import redis

    return redis.from_url(url, decode_responses=True)


class RedisQuoteStore:
    """读写全市场行情快照与涨幅榜。"""

    def __init__(self, client=None) -> None:
        self._client = client or create_redis_client()

    @property
    def client(self):
        return self._client

    def ping(self) -> bool:
        return bool(self._client.ping())

    def write_quotes(self, quotes: dict[str, QuoteSnapshot]) -> int:
        if not quotes:
            return 0

        pipe = self._client.pipeline(transaction=False)
        rank_members: list[tuple[float, str]] = []

        for tf_symbol, quote in quotes.items():
            pipe.hset(quote_key(tf_symbol), mapping=quote.to_redis_hash())
            rank_members.append((quote.change_pct, tf_symbol))

        pipe.delete(RANK_CHANGE_PCT_KEY)
        if rank_members:
            pipe.zadd(RANK_CHANGE_PCT_KEY, {member: score for score, member in rank_members})
        pipe.set(META_UPDATED_AT_KEY, datetime.now().isoformat(timespec="seconds"))
        pipe.set(META_QUOTE_COUNT_KEY, str(len(quotes)))
        pipe.execute()
        return len(quotes)

    def get_quotes(self, tf_symbols: list[str]) -> dict[str, QuoteSnapshot]:
        if not tf_symbols:
            return {}

        pipe = self._client.pipeline(transaction=False)
        for tf_symbol in tf_symbols:
            pipe.hgetall(quote_key(tf_symbol))
        rows = pipe.execute()

        fallback_time = normalize_datetime_text(self.get_updated_at() or "")

        result: dict[str, QuoteSnapshot] = {}
        for tf_symbol, data in zip(tf_symbols, rows, strict=True):
            if not data:
                continue
            quote = QuoteSnapshot.from_redis_hash(data)
            if not quote:
                continue
            if not quote.trade_time.strip() and fallback_time:
                quote.trade_time = fallback_time
            result[tf_symbol] = quote
        return result

    def get_rank_symbols(self, offset: int, limit: int) -> tuple[list[str], int]:
        total = int(self._client.zcard(RANK_CHANGE_PCT_KEY) or 0)
        if total == 0 or limit <= 0:
            return [], total
        symbols = self._client.zrevrange(
            RANK_CHANGE_PCT_KEY,
            offset,
            offset + limit - 1,
        )
        return list(symbols), total

    def list_all_rank_symbols(self) -> list[str]:
        return list(self._client.zrevrange(RANK_CHANGE_PCT_KEY, 0, -1))

    def get_updated_at(self) -> str | None:
        value = self._client.get(META_UPDATED_AT_KEY)
        return str(value) if value else None
