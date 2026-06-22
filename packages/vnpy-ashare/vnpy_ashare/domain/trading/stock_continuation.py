"""自选信号区：个股延续与统计展望（价量口径，P0）。"""

from __future__ import annotations

from vnpy_ashare.domain.market.sector_flow import SectorFlowOutlookDay
from vnpy_common.domain.base import FrozenModel

STOCK_CONTINUATION_DISCLAIMER = "统计情景，非走势预测"
STOCK_OUTLOOK_HORIZON_DAYS = 3

_BIAS_COMPACT = {"偏多": "多", "偏空": "空", "震荡": "震"}


def format_bias_compact(days) -> str:
    """将展望日 bias 序列格式化为 多/空/震。"""
    if not days:
        return "—"
    parts = [_BIAS_COMPACT.get(getattr(day, "bias", ""), "震") for day in days]
    return "/".join(parts)


class StockContinuationSnapshot(FrozenModel):
    """单票延续快照：与 SignalSnapshot 分离缓存。"""

    vt_symbol: str
    as_of: str = ""
    headline_pattern: str = "—"
    outlook_days: tuple[SectorFlowOutlookDay, ...] = ()
    composite_strength: float = 0.0
    price_pattern: str = "—"
    moneyflow_pattern: str | None = None
    signal_streak: int = 0
    rationale: str = ""
    sector_name: str = ""
    sector_id: str = ""
    sector_pattern: str = ""
    sector_outlook_compact: str = ""
    disclaimer: str = STOCK_CONTINUATION_DISCLAIMER


def format_outlook_compact(snapshot: StockContinuationSnapshot | None) -> str:
    """未来 3 日紧凑展示，如 多/多/震。"""
    if snapshot is None:
        return "—"
    return format_bias_compact(snapshot.outlook_days)
