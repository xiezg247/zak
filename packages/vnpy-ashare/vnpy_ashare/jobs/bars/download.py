"""全 A 股日 K 批量下载（统一起点 2020-01-01）。"""

from __future__ import annotations

import json
import logging
import time
import traceback
from datetime import datetime
from typing import Literal

from pydantic import Field
from vnpy.trader.constant import Interval

from vnpy_ashare.data.bar_store import iter_bar_overviews
from vnpy_ashare.data.bars import download_bars
from vnpy_ashare.data.download_concurrency import download_max_workers, run_parallel_map
from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.domain.symbols import StockItem
from vnpy_ashare.integrations.tushare.client import TushareNotConfiguredError, get_tushare_pro
from vnpy_ashare.jobs.core.progress import job_log, job_progress
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.storage.connection import get_meta, set_meta
from vnpy_ashare.storage.repositories.universe import load_universe_rows, universe_exists

_logger = logging.getLogger(__name__)

DEFAULT_UNIVERSE_DAILY_START = "2020-01-01"
_NO_DATA_SKIP_META_KEY = "universe_download_no_data_skips"
_NO_DATA_ERROR_MARKER = "未获取到数据"


class _DownloadOutcome(FrozenModel):
    vt_symbol: str = Field(description="VeighNa 合约代码")
    status: Literal["ok", "skipped", "failed"] = Field(description="下载结果状态")
    reason: str = Field(description="失败或跳过原因")


def parse_universe_daily_start(value: str | datetime | None = None) -> datetime:
    """解析全市场日 K 统一起点。"""
    if value is None:
        value = DEFAULT_UNIVERSE_DAILY_START
    if isinstance(value, datetime):
        return value.replace(hour=0, minute=0, second=0, microsecond=0)
    return datetime.strptime(str(value).strip()[:10], "%Y-%m-%d")


def _load_no_data_skips() -> set[str]:
    raw = get_meta(_NO_DATA_SKIP_META_KEY)
    if not raw:
        return set()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return set()
    if not isinstance(payload, dict):
        return set()
    return {str(key) for key in payload}


def _record_no_data_skip(vt_symbol: str, *, reason: str) -> None:
    raw = get_meta(_NO_DATA_SKIP_META_KEY) or "{}"
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    payload[vt_symbol] = {
        "reason": reason,
        "recorded_at": datetime.now().isoformat(timespec="seconds"),
    }
    set_meta(_NO_DATA_SKIP_META_KEY, json.dumps(payload, ensure_ascii=False))


def _is_no_data_error(exc: BaseException) -> bool:
    return isinstance(exc, RuntimeError) and _NO_DATA_ERROR_MARKER in str(exc)


def load_universe_stock_items() -> list[StockItem]:
    return [StockItem(symbol=symbol, exchange=exchange, name=name) for symbol, exchange, name in load_universe_rows()]


def select_universe_daily_targets(
    items: list[StockItem],
    *,
    unified_start: datetime,
    skip_no_data: set[str] | None = None,
) -> list[StockItem]:
    """筛选需下载日 K 的全市场标的（尚无 overview，或起点晚于统一起点）。"""
    overviews = {(row.symbol, row.exchange): row for row in iter_bar_overviews(scope="daily")}
    skipped = skip_no_data or set()
    unified_date = unified_start.date()
    targets: list[StockItem] = []
    for item in items:
        if item.vt_symbol in skipped:
            continue
        overview = overviews.get((item.symbol, item.exchange))
        if overview is None:
            targets.append(item)
            continue
        if overview.start.date() > unified_date:
            targets.append(item)
    return targets


def _download_one(
    item: StockItem,
    *,
    start: datetime,
    end: datetime,
) -> _DownloadOutcome:
    try:
        download_bars(
            symbol=item.symbol,
            exchange=item.exchange,
            interval=Interval.DAILY,
            start=start,
            end=end,
            output=lambda _msg: None,
        )
        job_log(f"✓ {item.vt_symbol}")
        return _DownloadOutcome(vt_symbol=item.vt_symbol, status="ok", reason="")
    except Exception as ex:
        if _is_no_data_error(ex):
            reason = str(ex)
            _record_no_data_skip(item.vt_symbol, reason=reason)
            _logger.info("跳过 %s：Tushare 无日 K（已记入跳过列表，下次不再重试）", item.vt_symbol)
            job_log(f"− {item.vt_symbol} 无数据")
            return _DownloadOutcome(vt_symbol=item.vt_symbol, status="skipped", reason=reason)
        msg = traceback.format_exc().strip().split("\n")[-1]
        _logger.warning("下载 %s 失败: %s", item.vt_symbol, msg)
        job_log(f"✗ {item.vt_symbol} {msg}")
        return _DownloadOutcome(vt_symbol=item.vt_symbol, status="failed", reason=msg)


def batch_download_universe_daily_bars(
    *,
    daily_start: str | datetime | None = None,
    delay: float = 0.3,
    max_workers: int | None = None,
) -> JobResult:
    """为全 A 股列表下载/补全自统一起点以来的日 K（Tushare Pro）。"""
    if not universe_exists():
        return JobResult(
            success=False,
            message="全 A 股列表不存在，请先运行「同步 A 股列表」",
        )

    try:
        get_tushare_pro()
    except TushareNotConfiguredError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    items = load_universe_stock_items()
    if not items:
        return JobResult(success=False, message="全 A 股列表为空，请先同步标的")

    start = parse_universe_daily_start(daily_start)
    start_text = start.strftime("%Y-%m-%d")
    targets = select_universe_daily_targets(items, unified_start=start, skip_no_data=_load_no_data_skips())
    if not targets:
        skipped_count = len(_load_no_data_skips())
        suffix = f"，{skipped_count} 只已标记为数据源无 K 线" if skipped_count else ""
        job_log(f"全市场 {len(items)} 只日 K 均已覆盖自 {start_text}{suffix}")
        return JobResult(
            success=True,
            message=f"全市场 {len(items)} 只日 K 均已覆盖自 {start_text}（增量由「补全本地日 K」维护{suffix}）",
        )

    end = datetime.now()
    workers = max_workers if max_workers is not None else download_max_workers(item_count=len(targets))
    job_log(f"待下载 {len(targets)} 只 · 自 {start_text} · 并发 {workers}")

    def on_complete(index: int, item: StockItem, outcome: _DownloadOutcome) -> None:
        job_progress(index, len(targets), item.vt_symbol)

    if workers <= 1:
        outcomes: list[_DownloadOutcome] = []
        for index, item in enumerate(targets, start=1):
            outcomes.append(_download_one(item, start=start, end=end))
            job_progress(index, len(targets), item.vt_symbol)
            if index < len(targets) and delay > 0:
                time.sleep(delay)
    else:
        outcomes = run_parallel_map(
            targets,
            lambda item: _download_one(item, start=start, end=end),
            max_workers=workers,
            on_complete=on_complete,
        )

    success = sum(1 for item in outcomes if item.status == "ok")
    skipped = sum(1 for item in outcomes if item.status == "skipped")
    failed = [(item.vt_symbol, item.reason) for item in outcomes if item.status == "failed"]

    summary = f"全市场日 K：完成 {success}/{len(targets)} 只（自 {start_text}）"
    if skipped:
        summary += f"；跳过 {skipped} 只（数据源无 K 线）"
    if failed:
        detail = "; ".join(f"{symbol}: {reason}" for symbol, reason in failed[:3])
        if len(failed) > 3:
            detail += f" 等共 {len(failed)} 只"
        return JobResult(success=False, message=f"{summary}；失败 {len(failed)}（{detail}）")
    return JobResult(success=True, message=summary)
