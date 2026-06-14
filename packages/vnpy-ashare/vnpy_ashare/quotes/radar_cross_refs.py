"""雷达展望 / 选股 / 共振交叉引用。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar_models import RadarRow
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


def build_outlook_cross_ref_suffix(rows: tuple[RadarRow, ...]) -> str:
    """展望卡副标题后缀：与最新选股结果重合数。"""
    if not rows:
        return ""
    recipe = latest_recipe_vt_symbols()
    if not recipe:
        return ""
    overlap = sum(1 for row in rows if row.vt_symbol in recipe)
    if overlap <= 0:
        return ""
    return f"选股重合 {overlap}"


def build_outlook_cross_ref_hint(rows: tuple[RadarRow, ...]) -> str:
    recipe = latest_recipe_vt_symbols()
    if not recipe or not rows:
        return ""
    names: list[str] = []
    for row in rows:
        if row.vt_symbol in recipe:
            names.append(row.name or row.symbol)
        if len(names) >= 5:
            break
    if not names:
        return ""
    return "与最新选股重合：" + "、".join(names)
