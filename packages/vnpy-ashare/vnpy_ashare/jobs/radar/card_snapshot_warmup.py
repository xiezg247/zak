"""雷达统计/发现卡片磁盘快照预热。"""

from __future__ import annotations

from vnpy_ashare.domain.time.china import china_now
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.quotes.radar.loaders.load import RADAR_SNAPSHOT_CARD_IDS, load_radar_cards_batch


def warm_radar_card_snapshots_job(*, force: bool = False) -> JobResult:
    """交易时段批量重算雷达重卡并写入 ``radar_card_snapshot`` 表。"""
    now = china_now()
    if not force and not is_ashare_trading_session(now):
        return JobResult(success=True, skipped=True, message="非交易时段，已跳过")

    items = [(card_id, {"force_recompute": force}) for card_id in sorted(RADAR_SNAPSHOT_CARD_IDS)]
    loaded, errors = load_radar_cards_batch(items)
    if errors and not loaded:
        first_id = next(iter(errors))
        return JobResult(success=False, message=f"{first_id}: {errors[first_id]}")

    parts = [f"已预热 {len(loaded)} 张"]
    if errors:
        parts.append(f"失败 {len(errors)} 张")
    return JobResult(success=True, message=" · ".join(parts))
