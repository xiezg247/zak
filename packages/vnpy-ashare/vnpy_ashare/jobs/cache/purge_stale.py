"""清理 cache schema 中过期或可重建的缓存行。"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.storage.repositories.cache_stores import (
    _position_cache_repo,
    _radar_ai_hint_repo,
    _radar_horizon_repo,
    _radar_predict_repo,
    _sector_outlook_repo,
    _signal_cache_repo,
)


def _env_int(key: str, default: int) -> int:
    raw = os.getenv(key, str(default)).strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def purge_stale_cache_job() -> JobResult:
    """删除过期 LLM/雷达 hint 与过旧自选策略磁盘缓存。"""
    now = datetime.now()
    now_text = now.isoformat(timespec="seconds")
    signal_cutoff = (now - timedelta(days=_env_int("CACHE_SIGNAL_RETENTION_DAYS", 7))).isoformat(timespec="seconds")
    position_cutoff = signal_cutoff
    radar_snapshot_cutoff = (now - timedelta(days=_env_int("CACHE_RADAR_SNAPSHOT_RETENTION_DAYS", 30))).isoformat(timespec="seconds")

    deleted: dict[str, int] = {
        "radar_ai_hint": _radar_ai_hint_repo.delete_expired_before(now_text),
        "sector_flow_outlook_llm": _sector_outlook_repo.delete_expired_before(now_text),
        "watchlist_signal": _signal_cache_repo.delete_updated_before(signal_cutoff),
        "watchlist_position": _position_cache_repo.delete_updated_before(position_cutoff),
        "radar_predict": _radar_predict_repo.delete_computed_before(radar_snapshot_cutoff),
        "radar_horizon": _radar_horizon_repo.delete_computed_before(radar_snapshot_cutoff),
    }

    total = sum(deleted.values())
    parts = ", ".join(f"{name} {count}" for name, count in deleted.items() if count)
    detail = parts or "无过期行"
    return JobResult(success=True, message=f"清理 cache {total} 行（{detail}）")
