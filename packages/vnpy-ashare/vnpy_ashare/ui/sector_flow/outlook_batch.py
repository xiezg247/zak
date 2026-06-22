"""板块展望策略批量扫描（纯逻辑，便于单测）。"""

from __future__ import annotations

from vnpy_ashare.domain.market.sector_flow import SectorFlowRow

OUTLOOK_BATCH_SCAN_MAX = 5


def prepare_batch_sector_scans(
    sectors: list[SectorFlowRow],
    *,
    max_count: int = OUTLOOK_BATCH_SCAN_MAX,
) -> tuple[list[SectorFlowRow], str | None]:
    """去重并截断批量扫描名单。返回 (待扫板块, 提示语)。"""
    seen: set[str] = set()
    unique: list[SectorFlowRow] = []
    for sector in sectors:
        sector_id = str(sector.sector_id or "").strip()
        if not sector_id or sector_id in seen:
            continue
        seen.add(sector_id)
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
