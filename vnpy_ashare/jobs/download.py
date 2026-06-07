"""自选池批量下载日 K。"""

from __future__ import annotations

import time
from datetime import datetime

from vnpy.trader.constant import Interval

from vnpy_ashare.bars import download_bars, load_watchlist
from vnpy_ashare.jobs.result import JobResult


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
    failed: list[str] = []

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
            failed.append(item.vt_symbol)

        if index < len(items) and delay > 0:
            time.sleep(delay)

    if failed:
        return JobResult(
            success=False,
            message=f"完成：成功 {success}，失败 {len(failed)}（{', '.join(failed[:5])}）",
        )
    return JobResult(success=True, message=f"已下载 {success} 只自选日 K")
