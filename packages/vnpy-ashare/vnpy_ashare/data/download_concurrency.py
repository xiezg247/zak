"""K 线下载任务有限并发（TickFlow / datafeed 拉取）。"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextvars import copy_context
from typing import TypeVar

from vnpy_ashare.config.constants.concurrency import (
    CAP_AVG_TURNOVER_PREFETCH_MAX_WORKERS,
    CAP_CONCEPT_MEMBER_MAX_WORKERS,
    CAP_CONCEPT_PREFETCH_MAX_WORKERS,
    CAP_CONTINUATION_BATCH_MAX_WORKERS,
    CAP_DOWNLOAD_MAX_WORKERS,
    CAP_INTRADAY_SEAL_TIME_MAX_WORKERS,
    CAP_MCP_INTRADAY_FLOW_MAX_WORKERS,
    CAP_MONEYFLOW_PREFETCH_MAX_WORKERS,
    CAP_RADAR_BOARD_MAX_WORKERS,
    CAP_RELATIVE_INDEX_ENRICH_MAX_WORKERS,
    CAP_SECTOR_FLOW_SYNC_MAX_WORKERS,
    CAP_TUSHARE_ANCHOR_PREFETCH_MAX_WORKERS,
    CAP_TUSHARE_PREFETCH_STAGE_MAX_WORKERS,
    DEFAULT_AVG_TURNOVER_PREFETCH_MAX_WORKERS,
    DEFAULT_CONCEPT_MEMBER_MAX_WORKERS,
    DEFAULT_CONCEPT_PREFETCH_MAX_WORKERS,
    DEFAULT_CONTINUATION_BATCH_MAX_WORKERS,
    DEFAULT_DOWNLOAD_MAX_WORKERS,
    DEFAULT_INTRADAY_SEAL_TIME_MAX_WORKERS,
    DEFAULT_MCP_INTRADAY_FLOW_MAX_WORKERS,
    DEFAULT_MONEYFLOW_PREFETCH_MAX_WORKERS,
    DEFAULT_RADAR_BOARD_MAX_WORKERS,
    DEFAULT_RELATIVE_INDEX_ENRICH_MAX_WORKERS,
    DEFAULT_SECTOR_FLOW_SYNC_MAX_WORKERS,
    DEFAULT_TUSHARE_ANCHOR_PREFETCH_MAX_WORKERS,
    DEFAULT_TUSHARE_PREFETCH_STAGE_MAX_WORKERS,
    ENV_AVG_TURNOVER_PREFETCH_MAX_WORKERS,
    ENV_CONCEPT_MEMBER_MAX_WORKERS,
    ENV_CONCEPT_PREFETCH_MAX_WORKERS,
    ENV_CONTINUATION_BATCH_MAX_WORKERS,
    ENV_DOWNLOAD_MAX_WORKERS,
    ENV_INTRADAY_SEAL_TIME_MAX_WORKERS,
    ENV_MCP_INTRADAY_FLOW_MAX_WORKERS,
    ENV_MONEYFLOW_PREFETCH_MAX_WORKERS,
    ENV_RADAR_BOARD_MAX_WORKERS,
    ENV_RELATIVE_INDEX_ENRICH_MAX_WORKERS,
    ENV_SECTOR_FLOW_SYNC_MAX_WORKERS,
    ENV_TUSHARE_ANCHOR_PREFETCH_MAX_WORKERS,
    ENV_TUSHARE_PREFETCH_STAGE_MAX_WORKERS,
)

T = TypeVar("T")
R = TypeVar("R")

_RETRY_DELAY_SEC = 0.5
_MAX_ATTEMPTS = 2


class _Unset:
    """并行槽位占位：与 worker 返回的 None 区分。"""

    __slots__ = ()


_UNSET = _Unset()


def env_max_workers(
    env_key: str,
    default: int,
    *,
    item_count: int,
    cap: int,
) -> int:
    """读取环境变量并返回 ``min(configured, item_count)``。"""
    if item_count <= 0:
        return 1
    raw = os.getenv(env_key, str(default)).strip()
    try:
        configured = int(raw)
    except ValueError:
        configured = default
    configured = max(1, min(configured, cap))
    return min(configured, item_count)


def download_max_workers(*, item_count: int) -> int:
    """并发下载 worker 数（DOWNLOAD_MAX_WORKERS，默认 3，上限 6）。"""
    return env_max_workers(
        ENV_DOWNLOAD_MAX_WORKERS,
        DEFAULT_DOWNLOAD_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_DOWNLOAD_MAX_WORKERS,
    )


def mcp_intraday_flow_max_workers(*, item_count: int) -> int:
    """MCP 盘中资金流（MCP_INTRADAY_FLOW_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_MCP_INTRADAY_FLOW_MAX_WORKERS,
        DEFAULT_MCP_INTRADAY_FLOW_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_MCP_INTRADAY_FLOW_MAX_WORKERS,
    )


def concept_member_max_workers(*, item_count: int) -> int:
    """同花顺概念成分（CONCEPT_MEMBER_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_CONCEPT_MEMBER_MAX_WORKERS,
        DEFAULT_CONCEPT_MEMBER_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_CONCEPT_MEMBER_MAX_WORKERS,
    )


def concept_prefetch_max_workers(*, item_count: int = 2) -> int:
    """概念板预拉 index/daily 并行（CONCEPT_PREFETCH_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_CONCEPT_PREFETCH_MAX_WORKERS,
        DEFAULT_CONCEPT_PREFETCH_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_CONCEPT_PREFETCH_MAX_WORKERS,
    )


def sector_flow_sync_max_workers(*, item_count: int) -> int:
    """板块资金日同步（SECTOR_FLOW_SYNC_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_SECTOR_FLOW_SYNC_MAX_WORKERS,
        DEFAULT_SECTOR_FLOW_SYNC_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_SECTOR_FLOW_SYNC_MAX_WORKERS,
    )


def moneyflow_prefetch_max_workers(*, item_count: int) -> int:
    """moneyflow 预拉（MONEYFLOW_PREFETCH_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_MONEYFLOW_PREFETCH_MAX_WORKERS,
        DEFAULT_MONEYFLOW_PREFETCH_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_MONEYFLOW_PREFETCH_MAX_WORKERS,
    )


def tushare_anchor_prefetch_max_workers(*, item_count: int) -> int:
    """Tushare anchor 后多数据集并行（TUSHARE_ANCHOR_PREFETCH_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_TUSHARE_ANCHOR_PREFETCH_MAX_WORKERS,
        DEFAULT_TUSHARE_ANCHOR_PREFETCH_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_TUSHARE_ANCHOR_PREFETCH_MAX_WORKERS,
    )


def tushare_prefetch_stage_max_workers(*, item_count: int = 2) -> int:
    """Tushare 预拉阶段并行（anchor 与 stock_basic，TUSHARE_PREFETCH_STAGE_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_TUSHARE_PREFETCH_STAGE_MAX_WORKERS,
        DEFAULT_TUSHARE_PREFETCH_STAGE_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_TUSHARE_PREFETCH_STAGE_MAX_WORKERS,
    )


def avg_turnover_prefetch_max_workers(*, item_count: int) -> int:
    """平均换手率 preload（AVG_TURNOVER_PREFETCH_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_AVG_TURNOVER_PREFETCH_MAX_WORKERS,
        DEFAULT_AVG_TURNOVER_PREFETCH_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_AVG_TURNOVER_PREFETCH_MAX_WORKERS,
    )


def continuation_batch_max_workers(*, item_count: int) -> int:
    """自选延续 batch（CONTINUATION_BATCH_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_CONTINUATION_BATCH_MAX_WORKERS,
        DEFAULT_CONTINUATION_BATCH_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_CONTINUATION_BATCH_MAX_WORKERS,
    )


def relative_index_enrich_max_workers(*, item_count: int) -> int:
    """相对指数 enrich batch（RELATIVE_INDEX_ENRICH_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_RELATIVE_INDEX_ENRICH_MAX_WORKERS,
        DEFAULT_RELATIVE_INDEX_ENRICH_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_RELATIVE_INDEX_ENRICH_MAX_WORKERS,
    )


def intraday_seal_time_max_workers(*, item_count: int) -> int:
    """TickFlow 触板时间补拉（INTRADAY_SEAL_TIME_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_INTRADAY_SEAL_TIME_MAX_WORKERS,
        DEFAULT_INTRADAY_SEAL_TIME_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_INTRADAY_SEAL_TIME_MAX_WORKERS,
    )


def radar_board_max_workers(*, item_count: int) -> int:
    """雷达整板卡片并行（RADAR_BOARD_MAX_WORKERS）。"""
    return env_max_workers(
        ENV_RADAR_BOARD_MAX_WORKERS,
        DEFAULT_RADAR_BOARD_MAX_WORKERS,
        item_count=item_count,
        cap=CAP_RADAR_BOARD_MAX_WORKERS,
    )


def _is_retryable(exc: BaseException) -> bool:
    message = str(exc).lower()
    return "locked" in message or "timeout" in message or "429" in message or "rate" in message or "频率超限" in message


def run_with_retry(func: Callable[[], R]) -> R:
    """遇数据库锁 / 限流时短暂退避重试。"""
    last_exc: BaseException | None = None
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return func()
        except BaseException as ex:
            last_exc = ex
            if attempt + 1 >= _MAX_ATTEMPTS or not _is_retryable(ex):
                raise
            message = str(ex)
            if "频率超限" in message:
                time.sleep(62.0)
            else:
                time.sleep(_RETRY_DELAY_SEC * (attempt + 1))
    assert last_exc is not None
    raise last_exc


def run_parallel_map(
    items: list[T],
    worker: Callable[[T], R],
    *,
    max_workers: int | None = None,
    on_complete: Callable[[int, T, R], None] | None = None,
) -> list[R]:
    """并行执行 worker，返回与 items 同序的结果列表。

    worker 可合法返回 ``None``；仅 future 未完成时视为缺失结果。
    """
    if not items:
        return []

    workers = max_workers if max_workers is not None else download_max_workers(item_count=len(items))
    if workers <= 1 or len(items) <= 1:
        results: list[R] = []
        for index, item in enumerate(items):

            def _invoke(current: T = item) -> R:
                return worker(current)

            result = run_with_retry(_invoke)
            results.append(result)
            if on_complete is not None:
                on_complete(index, item, result)
        return results

    ordered: list[R | _Unset] = [_UNSET] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_map = {pool.submit(copy_context().run, run_with_retry, lambda item=item: worker(item)): (index, item) for index, item in enumerate(items)}
        for future in as_completed(future_map):
            index, item = future_map[future]
            result = future.result()
            ordered[index] = result
            if on_complete is not None:
                on_complete(index, item, result)
    if _UNSET in ordered:
        raise RuntimeError("parallel map missing results")
    return ordered  # type: ignore[return-value]
