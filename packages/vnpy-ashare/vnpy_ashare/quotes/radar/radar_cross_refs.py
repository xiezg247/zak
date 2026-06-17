"""雷达展望 / 选股 / 共振交叉引用。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.radar_models import RadarRow
from vnpy_ashare.quotes.radar.radar_resonance_store import get_radar_resonance_entries
from vnpy_ashare.screener.run.run_store import get_latest_run


def latest_recipe_vt_symbols(limit: int = 200) -> set[str]:
    record = get_latest_run()
    if record is None or not record.rows:
        return set()
    symbols: set[str] = set()
    for row in record.rows[:limit]:
        vt = str(row.get("vt_symbol") or "").strip()
        if vt:
            symbols.add(vt)
    return symbols


def latest_resonance_vt_symbols(limit: int = 200) -> set[str]:

    entries = get_radar_resonance_entries()
    symbols: set[str] = set()
    for entry in entries[:limit]:
        vt = str(entry.vt_symbol or "").strip()
        if vt:
            symbols.add(vt)
    return symbols


def build_outlook_cross_ref_suffix(rows: tuple[RadarRow, ...]) -> str:
    """展望卡副标题后缀：与最新选股 / 共振列表重合数。"""
    if not rows:
        return ""
    parts: list[str] = []
    recipe = latest_recipe_vt_symbols()
    if recipe:
        overlap = sum(1 for row in rows if row.vt_symbol in recipe)
        if overlap > 0:
            parts.append(f"选股重合 {overlap}")
    resonance = latest_resonance_vt_symbols()
    if resonance:
        overlap = sum(1 for row in rows if row.vt_symbol in resonance)
        if overlap > 0:
            parts.append(f"共振重合 {overlap}")
    return " · ".join(parts)


def build_outlook_cross_ref_hint(rows: tuple[RadarRow, ...]) -> str:
    recipe = latest_recipe_vt_symbols()
    resonance = latest_resonance_vt_symbols()
    if not rows or (not recipe and not resonance):
        return ""
    names: list[str] = []
    for row in rows:
        if row.vt_symbol in recipe or row.vt_symbol in resonance:
            names.append(row.name or row.symbol)
        if len(names) >= 5:
            break
    if not names:
        return ""
    return "与最新选股/共振重合：" + "、".join(names)
