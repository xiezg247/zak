"""app schema 表（依赖 search_path 解析）。"""

from __future__ import annotations

from sqlalchemy import BigInteger, Column, Double, Integer, MetaData, PrimaryKeyConstraint, Table, Text, UUID, UniqueConstraint

metadata = MetaData()

meta = Table(
    "meta",
    metadata,
    Column("key", Text, primary_key=True),
    Column("value", Text, nullable=False),
)

watchlist = Table(
    "watchlist",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("symbol", Text, nullable=False),
    Column("exchange", Text, nullable=False),
    Column("name", Text, nullable=False, server_default=""),
    Column("sort_order", Integer, nullable=False, server_default="0"),
)

watchlist_group_members = Table(
    "watchlist_group_members",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("group_id", Text, nullable=False),
    Column("symbol", Text, nullable=False),
    Column("exchange", Text, nullable=False),
    PrimaryKeyConstraint("group_id", "symbol", "exchange"),
)

watchlist_groups = Table(
    "watchlist_groups",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    Column("position_cap_pct", Double),
)

stock_note_memos = Table(
    "stock_note_memos",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("symbol", Text, nullable=False),
    Column("exchange", Text, nullable=False),
    Column("body", Text, nullable=False, server_default=""),
    Column("updated_at", Text, nullable=False),
    PrimaryKeyConstraint("user_id", "symbol", "exchange"),
)

stock_note_entries = Table(
    "stock_note_entries",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("symbol", Text, nullable=False),
    Column("exchange", Text, nullable=False),
    Column("body", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

stock_analysis_reports = Table(
    "stock_analysis_reports",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("symbol", Text, nullable=False),
    Column("exchange", Text, nullable=False),
    Column("title", Text, nullable=False, server_default=""),
    Column("body", Text, nullable=False),
    Column("source_scope", Text, nullable=False, server_default=""),
    Column("context_json", Text, nullable=False, server_default=""),
    Column("summary", Text, nullable=False, server_default=""),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

trading_plans = Table(
    "trading_plans",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("trade_date", Text, nullable=False),
    Column("emotion_expected", Text, nullable=False, server_default=""),
    Column("max_position_pct", Double, nullable=False, server_default="0"),
    Column("notes", Text, nullable=False, server_default=""),
    Column("status", Text, nullable=False, server_default="draft"),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

trading_plan_symbols = Table(
    "trading_plan_symbols",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("plan_id", Text, nullable=False),
    Column("symbol", Text, nullable=False),
    Column("exchange", Text, nullable=False),
    Column("allowed_modes", Text, nullable=False, server_default=""),
    Column("entry_conditions", Text, nullable=False, server_default=""),
    Column("exit_conditions", Text, nullable=False, server_default=""),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    PrimaryKeyConstraint("plan_id", "symbol", "exchange"),
)

trading_playbook_sections = Table(
    "trading_playbook_sections",
    metadata,
    Column("section_id", Text, primary_key=True),
    Column("title", Text, nullable=False),
    Column("body_md", Text, nullable=False, server_default=""),
    Column("collapsed", Integer, nullable=False, server_default="0"),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    Column("updated_at", Text, nullable=False),
)

screener_schemes = Table(
    "screener_schemes",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("config_json", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

screener_recipes = Table(
    "screener_recipes",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("id", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("trigger_kind", Text, nullable=False),
    Column("config_json", Text, nullable=False),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

screener_runs = Table(
    "screener_runs",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("id", Text, primary_key=True),
    Column("condition", Text, nullable=False),
    Column("source", Text, nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("total_scanned", Integer, nullable=False, server_default="0"),
    Column("config_json", Text, nullable=False, server_default="{}"),
    Column("result_json", Text, nullable=False),
    Column("created_at", Text, nullable=False),
)

backtest_runs = Table(
    "backtest_runs",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("id", Text, primary_key=True),
    Column("vt_symbol", Text, nullable=False),
    Column("strategy", Text, nullable=False),
    Column("interval", Text, nullable=False, server_default="d"),
    Column("start_date", Text, nullable=False),
    Column("end_date", Text, nullable=False),
    Column("total_return", Double),
    Column("max_drawdown", Double),
    Column("sharpe_ratio", Double),
    Column("trade_count", Integer),
    Column("source", Text, nullable=False, server_default="single"),
    Column("batch_id", Text),
    Column("raw_statistics_json", Text, nullable=False, server_default="{}"),
    Column("created_at", Text, nullable=False),
)

feed_subscriptions = Table(
    "feed_subscriptions",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("id", Text, primary_key=True),
    Column("source_type", Text, nullable=False, server_default="bilibili_up"),
    Column("source_id", Text, nullable=False),
    Column("display_name", Text, nullable=False, server_default=""),
    Column("avatar_url", Text, nullable=False, server_default=""),
    Column("config_json", Text, nullable=False, server_default="{}"),
    Column("enabled", Integer, nullable=False, server_default="1"),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
    UniqueConstraint("source_type", "source_id"),
)

feed_items = Table(
    "feed_items",
    metadata,
    Column("id", Text, primary_key=True),
    Column("subscription_id", Text, nullable=False),
    Column("source_type", Text, nullable=False),
    Column("external_id", Text, nullable=False),
    Column("item_type", Text, nullable=False),
    Column("title", Text, nullable=False, server_default=""),
    Column("summary", Text, nullable=False, server_default=""),
    Column("url", Text, nullable=False),
    Column("author_name", Text, nullable=False, server_default=""),
    Column("published_at", Text, nullable=False),
    Column("payload_json", Text, nullable=False, server_default="{}"),
    Column("read_at", Text),
    Column("created_at", Text, nullable=False),
    UniqueConstraint("source_type", "external_id"),
)

feed_cursors = Table(
    "feed_cursors",
    metadata,
    Column("subscription_id", Text, primary_key=True),
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("last_video_ts", Integer, nullable=False, server_default="0"),
    Column("last_dynamic_id", Text, nullable=False, server_default=""),
    Column("last_ok_at", Text),
    Column("last_error", Text, nullable=False, server_default=""),
)

feed_item_reads = Table(
    "feed_item_reads",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("item_id", Text, nullable=False),
    Column("read_at", Text, nullable=False),
    PrimaryKeyConstraint("user_id", "item_id"),
)

universe = Table(
    "universe",
    metadata,
    Column("symbol", Text, nullable=False),
    Column("exchange", Text, nullable=False),
    Column("name", Text, nullable=False, server_default=""),
    PrimaryKeyConstraint("symbol", "exchange"),
)

tushare_factor_cache = Table(
    "tushare_factor_cache",
    metadata,
    Column("dataset", Text, nullable=False),
    Column("trade_date", Text, nullable=False, server_default=""),
    Column("fetched_at", Text, nullable=False),
    Column("payload", Text, nullable=False),
    PrimaryKeyConstraint("dataset", "trade_date"),
)

financial_reports = Table(
    "financial_reports",
    metadata,
    Column("ts_code", Text, nullable=False),
    Column("report_type", Text, nullable=False),
    Column("end_date", Text, nullable=False),
    Column("ann_date", Text, nullable=False, server_default=""),
    Column("period", Text, nullable=False, server_default=""),
    Column("source", Text, nullable=False, server_default="tushare"),
    Column("fetched_at", Text, nullable=False),
    Column("payload", Text, nullable=False),
    PrimaryKeyConstraint("ts_code", "report_type", "end_date"),
)

financial_snapshots = Table(
    "financial_snapshots",
    metadata,
    Column("ts_code", Text, nullable=False),
    Column("end_date", Text, nullable=False),
    Column("revenue", Double),
    Column("net_income", Double),
    Column("operate_profit", Double),
    Column("basic_eps", Double),
    Column("total_assets", Double),
    Column("total_liab", Double),
    Column("total_equity", Double),
    Column("ocf", Double),
    Column("icf", Double),
    Column("fcf_flow", Double),
    Column("free_cashflow", Double),
    Column("roe", Double),
    Column("gross_margin", Double),
    Column("net_margin", Double),
    Column("debt_ratio", Double),
    Column("current_ratio", Double),
    Column("revenue_yoy", Double),
    Column("net_income_yoy", Double),
    Column("roe_yoy", Double),
    Column("ocf_to_profit", Double),
    Column("computed_at", Text, nullable=False),
    PrimaryKeyConstraint("ts_code", "end_date"),
)

financial_sync_meta = Table(
    "financial_sync_meta",
    metadata,
    Column("ts_code", Text, primary_key=True),
    Column("last_sync_at", Text, nullable=False),
    Column("latest_end_date", Text, nullable=False, server_default=""),
    Column("latest_ann_date", Text, nullable=False, server_default=""),
    Column("sync_status", Text, nullable=False, server_default="ok"),
    Column("error_message", Text, nullable=False, server_default=""),
    Column("periods_count", Integer, nullable=False, server_default="0"),
    Column("last_access_at", Text, nullable=False, server_default=""),
)

watchlist_positions = Table(
    "watchlist_positions",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("symbol", Text, nullable=False),
    Column("exchange", Text, nullable=False),
    Column("cost_price", Double, nullable=False),
    Column("volume", Integer, nullable=False),
    Column("buy_date", Text, nullable=False),
    Column("notes", Text, nullable=False, server_default=""),
    Column("source", Text, nullable=False, server_default="manual"),
    Column("plan_pct", Double),
    Column("sort_order", Integer, nullable=False, server_default="0"),
    Column("created_at", Text, nullable=False),
    Column("updated_at", Text, nullable=False),
)

notify_delivery_log = Table(
    "notify_delivery_log",
    metadata,
    Column("id", Text, primary_key=True),
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("event_type", Text, nullable=False),
    Column("channel", Text, nullable=False, server_default="feishu"),
    Column("payload_json", Text, nullable=False, server_default=""),
    Column("status", Text, nullable=False),
    Column("error", Text, nullable=False, server_default=""),
    Column("created_at", Text, nullable=False),
)

trade_calendar = Table(
    "trade_calendar",
    metadata,
    Column("cal_date", Text, primary_key=True),
    Column("is_open", Integer, nullable=False),
)

valuation_history = Table(
    "valuation_history",
    metadata,
    Column("ts_code", Text, nullable=False),
    Column("trade_date", Text, nullable=False),
    Column("close", Double),
    Column("pe_ttm", Double),
    Column("pb", Double),
    Column("total_mv", Double),
    Column("circ_mv", Double),
    Column("turnover_rate", Double),
    Column("fetched_at", Text, nullable=False),
    PrimaryKeyConstraint("ts_code", "trade_date"),
)

disclosure_calendar = Table(
    "disclosure_calendar",
    metadata,
    Column("ts_code", Text, nullable=False),
    Column("end_date", Text, nullable=False),
    Column("pre_date", Text, nullable=False, server_default=""),
    Column("ann_date", Text, nullable=False, server_default=""),
    Column("actual_date", Text, nullable=False, server_default=""),
    Column("fetched_at", Text, nullable=False),
    PrimaryKeyConstraint("ts_code", "end_date"),
)

symbol_suspend_days = Table(
    "symbol_suspend_days",
    metadata,
    Column("symbol", Text, nullable=False),
    Column("exchange", Text, nullable=False),
    Column("cal_date", Text, nullable=False),
    Column("suspend_type", Text, nullable=False, server_default="S"),
    PrimaryKeyConstraint("symbol", "exchange", "cal_date"),
)

sector_flow_daily = Table(
    "sector_flow_daily",
    metadata,
    Column("trade_date", Text, nullable=False),
    Column("sector_kind", Text, nullable=False),
    Column("sector_id", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("change_pct", Double, nullable=False),
    Column("net_flow_yi", Double, nullable=False),
    Column("flow_source", Text, nullable=False, server_default=""),
    PrimaryKeyConstraint("trade_date", "sector_kind", "sector_id"),
)

sector_flow_intraday = Table(
    "sector_flow_intraday",
    metadata,
    Column("trade_date", Text, nullable=False),
    Column("sector_kind", Text, nullable=False),
    Column("sector_id", Text, nullable=False),
    Column("name", Text, nullable=False),
    Column("bucket_time", Text, nullable=False),
    Column("clock_minutes", Integer, nullable=False),
    Column("net_flow_yi", Double, nullable=False),
    Column("change_pct", Double, nullable=False, server_default="0"),
    PrimaryKeyConstraint("trade_date", "sector_kind", "sector_id", "bucket_time"),
)

emotion_limit_ladder_daily = Table(
    "emotion_limit_ladder_daily",
    metadata,
    Column("trade_date", Text, primary_key=True),
    Column("max_limit_times", Integer, nullable=False, server_default="0"),
    Column("max_board_vt_symbol", Text, nullable=False, server_default=""),
    Column("linked_board_vt_symbols", Text, nullable=False, server_default=""),
    Column("updated_at", Text, nullable=False),
)

trading_playbook_discipline_daily = Table(
    "trading_playbook_discipline_daily",
    metadata,
    Column("user_id", UUID(as_uuid=False), nullable=False),
    Column("trade_date", Text, nullable=False),
    Column("check_id", Text, nullable=False),
    Column("checked", Integer, nullable=False, server_default="0"),
    PrimaryKeyConstraint("user_id", "trade_date", "check_id"),
)
