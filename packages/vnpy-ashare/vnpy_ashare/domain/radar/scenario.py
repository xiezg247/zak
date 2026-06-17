"""雷达未来情景领域模型。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.trading.signal_snapshot import SignalSnapshot
from vnpy_common.domain.base import FrozenModel


class ScenarioMetrics(FrozenModel):
    snapshot: SignalSnapshot = Field(description="信号快照")
    momentum_pct: float | None = Field(description="动量涨跌幅（%）")
    daily_vol_pct: float | None = Field(description="日波动率（%）")
    band_move_pct: float | None = Field(description="参考带波动幅度（%）")
    band_lower: float | None = Field(description="参考带下沿")
    band_upper: float | None = Field(description="参考带上沿")
