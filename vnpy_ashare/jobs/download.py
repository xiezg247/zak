"""自选池批量下载日 K。"""

from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime

from vnpy.trader.constant import Interval

from vnpy_ashare.bars import download_bars, load_watchlist
from vnpy_ashare.jobs.result import JobResult

_logger = logging.getLogger(__name__)


def batch_download_watchlist(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    delay: float = 0.3,
) -> JobResult:
    items = load_watchlist()
    if not items:
        return JobResult(success=False, message="自选池为空，跳过下载")

    start = start or datetime(2020, 1, 1)
    end = end or datetime.now()

    success = 0
    failed: list[tuple[str, str]] = []

    for index, item in enumerate(items, start=1):
        try:
            download_bars(
                symbol=item.symbol,
                exchange=item.exchange,
                interval=Interval.DAILY,
                start=start,
                end=end,
                output=lambda _msg: None,
            )
            success += 1
        except Exception:
            msg = traceback.format_exc().strip().split("\n")[-1]
            _logger.warning("下载 %s 失败:\n%s", item.vt_symbol, traceback.format_exc())
            failed.append((item.vt_symbol, msg))

        if index < len(items) and delay > 0:
            time.sleep(delay)

    if failed:
        detail = "; ".join(f"{symbol}: {reason}" for symbol, reason in failed[:3])
        if len(failed) > 3:
            detail += f" 等共 {len(failed)} 只"
        return JobResult(
            success=False,
            message=f"完成：成功 {success}，失败 {len(failed)}（{detail}）",
        )
    return JobResult(success=True, message=f"已下载 {success} 只自选日 K")
