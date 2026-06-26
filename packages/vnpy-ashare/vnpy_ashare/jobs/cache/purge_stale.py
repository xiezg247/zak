"""清理 cache schema 中过期或可重建的缓存行。"""

from __future__ import annotations

import os
from datetime import datetime, timedelta

from vnpy_ashare.jobs.core.result import JobResult
from vnpy_common.storage.session import cache_session


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
    radar_snapshot_cutoff = (now - timedelta(days=_env_int("CACHE_RADAR_SNAPSHOT_RETENTION_DAYS", 30))).isoformat(
        timespec="seconds"
    )

    deleted: dict[str, int] = {}
    with cache_session("", "") as conn:
        conn.execute("DELETE FROM radar_ai_hint_cache WHERE expires_at <= ?", (now_text,))
        deleted["radar_ai_hint"] = conn.last_rowcount

        conn.execute("DELETE FROM sector_flow_outlook_llm_cache WHERE expires_at <= ?", (now_text,))
        deleted["sector_flow_outlook_llm"] = conn.last_rowcount

        conn.execute("DELETE FROM watchlist_signal_cache WHERE updated_at < ?", (signal_cutoff,))
        deleted["watchlist_signal"] = conn.last_rowcount

        conn.execute("DELETE FROM watchlist_position_cache WHERE updated_at < ?", (position_cutoff,))
        deleted["watchlist_position"] = conn.last_rowcount

        conn.execute("DELETE FROM radar_predict_cache WHERE computed_at < ?", (radar_snapshot_cutoff,))
        deleted["radar_predict"] = conn.last_rowcount

        conn.execute("DELETE FROM radar_horizon_cache WHERE computed_at < ?", (radar_snapshot_cutoff,))
        deleted["radar_horizon"] = conn.last_rowcount

    total = sum(deleted.values())
    parts = ", ".join(f"{name} {count}" for name, count in deleted.items() if count)
    detail = parts or "无过期行"
    return JobResult(success=True, message=f"清理 cache {total} 行（{detail}）")
