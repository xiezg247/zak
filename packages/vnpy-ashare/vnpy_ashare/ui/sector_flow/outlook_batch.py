"""板块展望策略批量扫描（纯逻辑，便于单测）。"""

from __future__ import annotations

from collections.abc import Iterable

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow

OUTLOOK_BATCH_SCAN_MAX = 5


def _sector_scan_key(sector: SectorFlowRow) -> str:
    sector_id = str(sector.sector_id or "").strip()
    if sector_id:
        return f"id:{sector_id}"
    name = str(sector.name or "").strip()
    if name:
        return f"name:{name}"
    return ""


def coerce_sector_flow_rows(value: object) -> list[SectorFlowRow]:
    """从 Qt 信号 payload 解析板块行。"""
    if isinstance(value, SectorFlowRow):
        return [value]
    if not isinstance(value, (list, tuple)):
        return []
    rows: list[SectorFlowRow] = []
    for item in value:
        if isinstance(item, SectorFlowRow):
            rows.append(item)
    return rows


def prepare_batch_sector_scans(
    sectors: Iterable[SectorFlowRow],
    *,
    max_count: int = OUTLOOK_BATCH_SCAN_MAX,
) -> tuple[list[SectorFlowRow], str | None]:
    """去重并截断批量扫描名单。返回 (待扫板块, 提示语)。"""
    seen: set[str] = set()
    unique: list[SectorFlowRow] = []
    for sector in sectors:
        key = _sector_scan_key(sector)
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(sector)
    if not unique:
        return [], "请先选择板块"
    if len(unique) > max_count:
        trimmed = unique[:max_count]
        hint = f"最多同时扫描 {max_count} 个板块，已取前 {max_count} 个"
        return trimmed, hint
    return unique, None


def format_batch_scan_summary(
    *,
    total: int,
    succeeded: int,
    failed: int,
    aligned: int,
    diverged: int,
) -> str:
    parts = [f"批量扫描完成 {succeeded}/{total}"]
    if failed:
        parts.append(f"失败 {failed}")
    if aligned or diverged:
        parts.append(f"同向 {aligned} · 背离 {diverged}")
    return " · ".join(parts)
