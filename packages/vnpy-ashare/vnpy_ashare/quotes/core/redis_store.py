"""Redis 行情存储：快照 HASH + 涨幅榜 ZSET。"""

from __future__ import annotations

import os
from datetime import datetime

import redis
from dotenv import load_dotenv

from vnpy_ashare.domain.market.quote_snapshot import QuoteSnapshot
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.domain.time.quote_time import normalize_datetime_text
from vnpy_ashare.quotes.core.enrich import backfill_rank_scores_from_zset, fill_missing_tushare_factors
from vnpy_ashare.quotes.core.quote_l1_cache import (
    clear_quote_l1_cache,
    quote_l1_enabled,
    swap_quotes,
    try_get_quotes,
    try_list_rank_symbols,
)
from vnpy_ashare.quotes.core.quote_redis_codec import encode_quote_hash, quote_compact_enabled
from vnpy_ashare.quotes.misc.speed_baseline import apply_change_speed_5m
from vnpy_ashare.quotes.rank.rank_engine import compute_intraday_change_pct
from vnpy_common.paths import ENV_FILE

KEY_PREFIX = "zak"
QUOTE_KEY_FMT = f"{KEY_PREFIX}:quote:{{symbol}}"
RANK_KEY_FMT = f"{KEY_PREFIX}:rank:{{field}}"
PRECOMPUTED_RANK_KEY_FMT = f"{KEY_PREFIX}:rank:precomputed:{{field}}"
RANK_CHANGE_PCT_KEY = f"{KEY_PREFIX}:rank:change_pct"
META_UPDATED_AT_KEY = f"{KEY_PREFIX}:meta:updated_at"
META_QUOTE_COUNT_KEY = f"{KEY_PREFIX}:meta:quote_count"

PRECOMPUTED_RANK_TOP_N = 200

RANK_REDIS_FIELDS: tuple[str, ...] = (
    "change_pct",
    "turnover_rate",
    "amount",
    "volume",
    "amplitude",
    "intraday_change_pct",
    "volume_ratio",
    "net_mf_amount",
    "change_speed_5m",
    "limit_times",
)
# 盘中可能暂无新值（如窗口刚滚动、盘后静止），保留上一版榜避免 UI 整榜为空
_RANK_PRESERVE_WHEN_EMPTY: frozenset[str] = frozenset({"change_speed_5m"})
# 全市场每轮采集都会写入的成员榜（无需 delete 重建）
_FULL_RANK_FIELDS: frozenset[str] = frozenset(
    {"change_pct", "turnover_rate", "amount", "volume", "amplitude", "intraday_change_pct"},
)
# 条件成员榜：未达标标的需 zrem
_SPARSE_RANK_FIELDS: frozenset[str] = frozenset(
    {"volume_ratio", "net_mf_amount", "change_speed_5m", "limit_times"},
)
# 单次 pipeline 命令数上限，避免全市场 ~5k 标的一次 hgetall 写 socket 超时
QUOTE_READ_BATCH_SIZE = 300


def _iter_symbol_batches(symbols: list[str], batch_size: int) -> list[list[str]]:
    if batch_size <= 0:
        return [symbols] if symbols else []
    return [symbols[index : index + batch_size] for index in range(0, len(symbols), batch_size)]


def quote_key(tf_symbol: str) -> str:
    return QUOTE_KEY_FMT.format(symbol=tf_symbol)


def rank_key(field: str) -> str:
    return RANK_KEY_FMT.format(field=field)


def precomputed_rank_key(field: str) -> str:
    return PRECOMPUTED_RANK_KEY_FMT.format(field=field)


def rank_precompute_enabled() -> bool:
    return os.getenv("ZAK_RANK_PRECOMPUTE", "").strip().lower() in {"1", "true", "yes", "on"}


def rank_incremental_enabled() -> bool:
    return os.getenv("ZAK_RANK_INCREMENTAL", "").strip().lower() in {"1", "true", "yes", "on"}


def _write_precomputed_rank(pipe, field: str, members: list[tuple[float, str]]) -> None:
    if not rank_precompute_enabled() or not members:
        return
    top = sorted(members, key=lambda item: item[0], reverse=True)[:PRECOMPUTED_RANK_TOP_N]
    pkey = precomputed_rank_key(field)
    pipe.delete(pkey)
    if top:
        pipe.rpush(pkey, *[member for _score, member in top])


def _write_rank_field(
    pipe,
    *,
    field: str,
    members: list[tuple[float, str]],
    quotes: dict[str, QuoteSnapshot],
) -> None:
    if not members and field in _RANK_PRESERVE_WHEN_EMPTY and is_ashare_trading_session():
        return

    key = rank_key(field)
    if rank_incremental_enabled():
        if field in _FULL_RANK_FIELDS:
            if members:
                pipe.zadd(key, {member: score for score, member in members})
        elif field in _SPARSE_RANK_FIELDS:
            member_scores = {member: score for score, member in members}
            for tf_symbol in quotes:
                if tf_symbol not in member_scores:
                    pipe.zrem(key, tf_symbol)
            if member_scores:
                pipe.zadd(key, member_scores)
        else:
            pipe.delete(key)
            if members:
                pipe.zadd(key, {member: score for score, member in members})
    else:
        pipe.delete(key)
        if members:
            pipe.zadd(key, {member: score for score, member in members})

    _write_precomputed_rank(pipe, field, members)


def create_redis_client():
    load_dotenv(ENV_FILE)
    url = os.getenv("REDIS_URL", "").strip() or "redis://127.0.0.1:6379/0"

    return redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


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

        apply_change_speed_5m(self._client, quotes)

        pipe = self._client.pipeline(transaction=False)
        rank_members: dict[str, list[tuple[float, str]]] = {field: [] for field in RANK_REDIS_FIELDS}

        for tf_symbol, quote in quotes.items():
            key = quote_key(tf_symbol)
            mapping = encode_quote_hash(quote)
            if quote_compact_enabled():
                pipe.delete(key)
            pipe.hset(key, mapping=mapping)
            rank_members["change_pct"].append((quote.change_pct, tf_symbol))
            rank_members["turnover_rate"].append((quote.turnover_rate, tf_symbol))
            rank_members["amount"].append((quote.amount, tf_symbol))
            rank_members["volume"].append((quote.volume, tf_symbol))
            rank_members["amplitude"].append((quote.amplitude, tf_symbol))
            rank_members["intraday_change_pct"].append((compute_intraday_change_pct(quote), tf_symbol))
            if quote.volume_ratio > 0:
                rank_members["volume_ratio"].append((quote.volume_ratio, tf_symbol))
            if quote.net_mf_amount != 0:
                rank_members["net_mf_amount"].append((quote.net_mf_amount, tf_symbol))
            if quote.change_speed_5m != 0:
                rank_members["change_speed_5m"].append((quote.change_speed_5m, tf_symbol))
            if quote.limit_times >= 1:
                rank_members["limit_times"].append((quote.limit_times, tf_symbol))

        for field in RANK_REDIS_FIELDS:
            _write_rank_field(pipe, field=field, members=rank_members[field], quotes=quotes)
        pipe.set(META_UPDATED_AT_KEY, datetime.now().isoformat(timespec="seconds"))
        pipe.set(META_QUOTE_COUNT_KEY, str(len(quotes)))
        pipe.execute()
        if quote_l1_enabled():
            swap_quotes(quotes, updated_at=self.get_updated_at(), complete=True)
        return len(quotes)

    def get_quotes(self, tf_symbols: list[str], *, enrich_factors: bool = True) -> dict[str, QuoteSnapshot]:
        if not tf_symbols:
            return {}

        if quote_l1_enabled():
            cached = try_get_quotes(tf_symbols)
            if cached is not None:
                if enrich_factors and cached:
                    fill_missing_tushare_factors(cached)
                    backfill_rank_scores_from_zset(self, cached)
                return cached

        rows: list[dict] = []
        for batch in _iter_symbol_batches(tf_symbols, QUOTE_READ_BATCH_SIZE):
            pipe = self._client.pipeline(transaction=False)
            for tf_symbol in batch:
                pipe.hgetall(quote_key(tf_symbol))
            rows.extend(pipe.execute())

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
        if enrich_factors and result:
            fill_missing_tushare_factors(result)
            backfill_rank_scores_from_zset(self, result)
        return result

    def get_rank_scores(self, field: str, tf_symbols: list[str]) -> dict[str, float]:
        if not tf_symbols:
            return {}
        key = rank_key(field)
        scores: list = []
        for batch in _iter_symbol_batches(tf_symbols, QUOTE_READ_BATCH_SIZE):
            pipe = self._client.pipeline(transaction=False)
            for tf_symbol in batch:
                pipe.zscore(key, tf_symbol)
            scores.extend(pipe.execute())
        result: dict[str, float] = {}
        for tf_symbol, score in zip(tf_symbols, scores, strict=True):
            if score is not None:
                result[tf_symbol] = float(score)
        return result

    def get_rank_symbols(
        self,
        offset: int,
        limit: int,
        *,
        field: str = "change_pct",
        ascending: bool = False,
    ) -> tuple[list[str], int]:
        key = rank_key(field)
        total = int(self._client.zcard(key) or 0)
        if total == 0 or limit <= 0:
            return [], total
        if (
            rank_precompute_enabled()
            and not ascending
            and offset < PRECOMPUTED_RANK_TOP_N
            and offset + limit <= PRECOMPUTED_RANK_TOP_N
        ):
            pkey = precomputed_rank_key(field)
            pre_len = int(self._client.llen(pkey) or 0)
            if pre_len > 0:
                end = min(offset + limit - 1, pre_len - 1)
                if offset <= end:
                    return list(self._client.lrange(pkey, offset, end)), total
        if ascending:
            symbols = self._client.zrange(key, offset, offset + limit - 1)
        else:
            symbols = self._client.zrevrange(key, offset, offset + limit - 1)
        return list(symbols), total

    def list_all_rank_symbols(
        self,
        *,
        field: str = "change_pct",
        ascending: bool = False,
    ) -> list[str]:
        if field == "change_pct" and not ascending and quote_l1_enabled():
            cached = try_list_rank_symbols()
            if cached:
                return cached
        key = rank_key(field)
        if ascending:
            return list(self._client.zrange(key, 0, -1))
        return list(self._client.zrevrange(key, 0, -1))

    def get_updated_at(self) -> str | None:
        value = self._client.get(META_UPDATED_AT_KEY)
        return str(value) if value else None


_shared_redis_store: RedisQuoteStore | None = None


def get_redis_quote_store() -> RedisQuoteStore:
    """进程内共享 RedisQuoteStore，避免重复建连。"""
    global _shared_redis_store
    if _shared_redis_store is None:
        _shared_redis_store = RedisQuoteStore()
    return _shared_redis_store


def reset_redis_quote_store() -> None:
    global _shared_redis_store
    _shared_redis_store = None
    clear_quote_l1_cache()
