"""雷达龙头选股完成通知（高阈值，默认关闭订阅）。"""

from __future__ import annotations

import os
from typing import Any

from vnpy_ashare.domain.screener.run_result import ScreenerRunResult

_DEFAULT_MIN_HITS = 3
_DEFAULT_MIN_TOP_SCORE = 65.0


def _env_int(name: str, *, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _env_float(name: str, *, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return max(0.0, float(raw))
    except ValueError:
        return default


def build_radar_leader_ready_payload(
    result: ScreenerRunResult,
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """命中数与龙一评分达阈值时返回通知 payload，否则 None。"""
    condition = str(result.condition or "")
    if "不宜新开" in condition:
        return None

    rows = list(result.rows)
    if not rows:
        return None

    min_hits = _env_int("NOTIFY_RADAR_LEADER_MIN_HITS", default=_DEFAULT_MIN_HITS)
    if len(rows) < min_hits:
        return None

    top = rows[0]
    top_score = float(top.get("leader_score") or 0)
    min_score = _env_float("NOTIFY_RADAR_LEADER_MIN_SCORE", default=_DEFAULT_MIN_TOP_SCORE)
    if top_score < min_score:
        return None

    cfg = dict(config or {})
    variant = str(cfg.get("leader_variant") or "mainline")
    dragon = next((row for row in rows if str(row.get("leader_tier") or "") == "dragon_1"), top)
    return {
        "condition": condition,
        "variant": variant,
        "hit_count": len(rows),
        "total_scanned": result.total_scanned,
        "top_symbol": str(dragon.get("symbol") or dragon.get("vt_symbol") or ""),
        "top_name": str(dragon.get("name") or ""),
        "top_score": top_score,
        "top_tier_label": str(dragon.get("leader_tier_label") or ""),
        "sector_name": str(dragon.get("sector_name") or ""),
    }
