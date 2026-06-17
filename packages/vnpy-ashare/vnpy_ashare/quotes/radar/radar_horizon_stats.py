"""雷达未来展望扫描统计（轻量类型，避免 radar_horizon_scan 循环依赖）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HorizonScanStats:
    scanned_total: int
    excluded_count: int
    prefilter_total: int
    refined_total: int
    kline_missing: int
