"""量比 / 放量维度去重（兼容入口；实现见 engine.dimensions.volume_dedup）。"""

from __future__ import annotations

from vnpy_ashare.screener.engine.dimensions.volume_dedup import (
    apply_volume_liquidity_dedup,
    build_volume_discovery_subtitle,
    volume_liquidity_dedup_factor,
)

__all__ = [
    "apply_volume_liquidity_dedup",
    "build_volume_discovery_subtitle",
    "volume_liquidity_dedup_factor",
]
