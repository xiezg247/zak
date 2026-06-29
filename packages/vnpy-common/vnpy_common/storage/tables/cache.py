"""cache schema 表定义。"""

from __future__ import annotations

from sqlalchemy import Column, Integer, MetaData, PrimaryKeyConstraint, Table, Text

metadata = MetaData(schema="cache")

watchlist_signal_cache = Table(
    "watchlist_signal_cache",
    metadata,
    Column("vt_symbol", Text, nullable=False),
    Column("config_key", Text, nullable=False),
    Column("bar_as_of", Text, nullable=False),
    Column("payload", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    PrimaryKeyConstraint("vt_symbol", "config_key", "bar_as_of"),
)

watchlist_position_cache = Table(
    "watchlist_position_cache",
    metadata,
    Column("vt_symbol", Text, nullable=False),
    Column("config_key", Text, nullable=False),
    Column("bar_as_of", Text, nullable=False),
    Column("position_key", Text, nullable=False),
    Column("payload", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    PrimaryKeyConstraint("vt_symbol", "config_key", "bar_as_of", "position_key"),
)

radar_predict_cache = Table(
    "radar_predict_cache",
    metadata,
    Column("variant", Text, primary_key=True),
    Column("rows_json", Text, nullable=False),
    Column("scanned_total", Integer, nullable=False, server_default="0"),
    Column("excluded_count", Integer, nullable=False, server_default="0"),
    Column("prefilter_total", Integer, nullable=False, server_default="0"),
    Column("refined_total", Integer, nullable=False, server_default="0"),
    Column("kline_missing", Integer, nullable=False, server_default="0"),
    Column("model_label", Text, nullable=False, server_default=""),
    Column("computed_at", Text, nullable=False),
)

radar_horizon_cache = Table(
    "radar_horizon_cache",
    metadata,
    Column("variant", Text, primary_key=True),
    Column("rows_json", Text, nullable=False),
    Column("scanned_total", Integer, nullable=False, server_default="0"),
    Column("excluded_count", Integer, nullable=False, server_default="0"),
    Column("prefilter_total", Integer, nullable=False, server_default="0"),
    Column("refined_total", Integer, nullable=False, server_default="0"),
    Column("kline_missing", Integer, nullable=False, server_default="0"),
    Column("strategy_key", Text, nullable=False, server_default=""),
    Column("computed_at", Text, nullable=False),
)

radar_ai_hint_cache = Table(
    "radar_ai_hint_cache",
    metadata,
    Column("cache_key", Text, primary_key=True),
    Column("card_id", Text, nullable=False),
    Column("variant", Text, nullable=False),
    Column("fingerprint", Text, nullable=False),
    Column("hint", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("expires_at", Text, nullable=False),
)

sector_flow_outlook_llm_cache = Table(
    "sector_flow_outlook_llm_cache",
    metadata,
    Column("cache_key", Text, primary_key=True),
    Column("sector_kind", Text, nullable=False),
    Column("strategy_key", Text, nullable=False, server_default=""),
    Column("fingerprint", Text, nullable=False),
    Column("forward_dates_json", Text, nullable=False),
    Column("rows_json", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    Column("expires_at", Text, nullable=False),
)

radar_card_snapshot = Table(
    "radar_card_snapshot",
    metadata,
    Column("card_id", Text, nullable=False),
    Column("variant_key", Text, nullable=False, server_default=""),
    Column("payload_json", Text, nullable=False),
    Column("computed_at", Text, nullable=False),
    PrimaryKeyConstraint("card_id", "variant_key"),
)
