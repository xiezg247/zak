"""cache schema 表 DDL。"""

from __future__ import annotations

CACHE_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS cache.radar_predict_cache (
        variant TEXT PRIMARY KEY,
        rows_json TEXT NOT NULL,
        scanned_total INTEGER NOT NULL DEFAULT 0,
        excluded_count INTEGER NOT NULL DEFAULT 0,
        prefilter_total INTEGER NOT NULL DEFAULT 0,
        refined_total INTEGER NOT NULL DEFAULT 0,
        kline_missing INTEGER NOT NULL DEFAULT 0,
        model_label TEXT NOT NULL DEFAULT '',
        computed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cache.radar_horizon_cache (
        variant TEXT PRIMARY KEY,
        rows_json TEXT NOT NULL,
        scanned_total INTEGER NOT NULL DEFAULT 0,
        excluded_count INTEGER NOT NULL DEFAULT 0,
        prefilter_total INTEGER NOT NULL DEFAULT 0,
        refined_total INTEGER NOT NULL DEFAULT 0,
        kline_missing INTEGER NOT NULL DEFAULT 0,
        strategy_key TEXT NOT NULL DEFAULT '',
        computed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cache.radar_ai_hint_cache (
        cache_key TEXT PRIMARY KEY,
        card_id TEXT NOT NULL,
        variant TEXT NOT NULL,
        fingerprint TEXT NOT NULL,
        hint TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cache.watchlist_signal_cache (
        vt_symbol TEXT NOT NULL,
        config_key TEXT NOT NULL,
        bar_as_of TEXT NOT NULL,
        payload TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (vt_symbol, config_key, bar_as_of)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cache.watchlist_position_cache (
        vt_symbol TEXT NOT NULL,
        config_key TEXT NOT NULL,
        bar_as_of TEXT NOT NULL,
        position_key TEXT NOT NULL,
        payload TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (vt_symbol, config_key, bar_as_of, position_key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cache.sector_flow_outlook_llm_cache (
        cache_key TEXT PRIMARY KEY,
        sector_kind TEXT NOT NULL,
        strategy_key TEXT NOT NULL DEFAULT '',
        fingerprint TEXT NOT NULL,
        forward_dates_json TEXT NOT NULL,
        rows_json TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        expires_at TEXT NOT NULL
    )
    """,
)

CACHE_DOWNGRADE = (
    "DROP TABLE IF EXISTS cache.sector_flow_outlook_llm_cache",
    "DROP TABLE IF EXISTS cache.watchlist_position_cache",
    "DROP TABLE IF EXISTS cache.watchlist_signal_cache",
    "DROP TABLE IF EXISTS cache.radar_ai_hint_cache",
    "DROP TABLE IF EXISTS cache.radar_horizon_cache",
    "DROP TABLE IF EXISTS cache.radar_predict_cache",
)
