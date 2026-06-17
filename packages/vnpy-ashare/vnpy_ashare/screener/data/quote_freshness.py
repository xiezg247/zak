"""Redis 行情快照新鲜度检查与选股前预热。"""

from __future__ import annotations

from datetime import datetime

from vnpy_ashare.config.constants.recipe import (
    DEFAULT_MAX_QUOTE_AGE_SECONDS,
    ENV_QUOTE_MAX_AGE_SEC,
)
from vnpy_ashare.domain.core.env import env_str
from vnpy_ashare.domain.time.market_hours import CHINA_TZ
from vnpy_ashare.jobs.quotes import collect_market_quotes
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore

DEFAULT_MAX_AGE_SECONDS = DEFAULT_MAX_QUOTE_AGE_SECONDS


def quote_snapshot_age_seconds() -> float | None:
    """返回 Redis 全市场快照距现在的秒数；无元数据时返回 None。"""
    store = RedisQuoteStore()
    updated_at = store.get_updated_at()
    if not updated_at:
        return None
    try:
        ts = datetime.fromisoformat(str(updated_at).strip())
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=CHINA_TZ)
    now = datetime.now(CHINA_TZ)
    return max(0.0, (now - ts.astimezone(CHINA_TZ)).total_seconds())


def max_quote_age_seconds() -> int:
    raw = env_str(ENV_QUOTE_MAX_AGE_SEC) or str(DEFAULT_MAX_AGE_SECONDS)
    try:
        return max(30, int(raw))
    except ValueError:
        return DEFAULT_MAX_AGE_SECONDS


def ensure_fresh_quotes_for_screening(
    *,
    max_age_seconds: int | None = None,
    collect_if_stale: bool = True,
) -> tuple[bool, str]:
    """选股前确保行情足够新；过时且允许时触发一次 ``collect_market_quotes``。"""
    limit = max_age_seconds if max_age_seconds is not None else max_quote_age_seconds()
    age = quote_snapshot_age_seconds()
    if age is not None and age <= limit:
        return True, f"行情 {int(age)} 秒前更新"

    if not collect_if_stale:
        if age is None:
            return False, "暂无全市场行情快照"
        return False, f"行情已过时 {int(age)} 秒（阈值 {limit}s）"

    result = collect_market_quotes()
    if not result.success:
        stale = f"（原快照 {int(age)}s 前）" if age is not None else ""
        return False, f"行情采集失败{stale}：{result.message}"

    fresh_age = quote_snapshot_age_seconds()
    if fresh_age is not None and fresh_age <= limit:
        return True, f"已刷新行情：{result.message}"
    return True, result.message
