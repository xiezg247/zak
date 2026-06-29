"""初始 PostgreSQL schema DDL（由 Alembic 001 引用）。"""

from __future__ import annotations

SCHEMAS = (
    "CREATE SCHEMA IF NOT EXISTS auth",
    "CREATE SCHEMA IF NOT EXISTS app",
    "CREATE SCHEMA IF NOT EXISTS chat",
    "CREATE SCHEMA IF NOT EXISTS cache",
    "CREATE SCHEMA IF NOT EXISTS system",
)

APP_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS app.meta (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.watchlist (
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        sort_order INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (symbol, exchange)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.watchlist_groups (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        position_cap_pct DOUBLE PRECISION
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.watchlist_group_members (
        group_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        PRIMARY KEY (group_id, symbol, exchange),
        FOREIGN KEY (group_id) REFERENCES app.watchlist_groups(id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_watchlist_group_members_symbol ON app.watchlist_group_members(symbol, exchange)",
    """
    CREATE TABLE IF NOT EXISTS app.watchlist_positions (
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        cost_price DOUBLE PRECISION NOT NULL,
        volume INTEGER NOT NULL,
        buy_date TEXT NOT NULL,
        notes TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT 'manual',
        plan_pct DOUBLE PRECISION,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (symbol, exchange)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.universe (
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        name TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (symbol, exchange)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_universe_symbol ON app.universe(symbol)",
    """
    CREATE TABLE IF NOT EXISTS app.trade_calendar (
        cal_date TEXT PRIMARY KEY,
        is_open INTEGER NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.tushare_factor_cache (
        dataset TEXT NOT NULL,
        trade_date TEXT NOT NULL DEFAULT '',
        fetched_at TEXT NOT NULL,
        payload TEXT NOT NULL,
        PRIMARY KEY (dataset, trade_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.financial_reports (
        ts_code TEXT NOT NULL,
        report_type TEXT NOT NULL,
        end_date TEXT NOT NULL,
        ann_date TEXT NOT NULL DEFAULT '',
        period TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT 'tushare',
        fetched_at TEXT NOT NULL,
        payload TEXT NOT NULL,
        PRIMARY KEY (ts_code, report_type, end_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_financial_reports_ts_type ON app.financial_reports(ts_code, report_type, end_date DESC)",
    """
    CREATE TABLE IF NOT EXISTS app.financial_snapshots (
        ts_code TEXT NOT NULL,
        end_date TEXT NOT NULL,
        revenue DOUBLE PRECISION,
        net_income DOUBLE PRECISION,
        operate_profit DOUBLE PRECISION,
        basic_eps DOUBLE PRECISION,
        total_assets DOUBLE PRECISION,
        total_liab DOUBLE PRECISION,
        total_equity DOUBLE PRECISION,
        ocf DOUBLE PRECISION,
        icf DOUBLE PRECISION,
        fcf_flow DOUBLE PRECISION,
        free_cashflow DOUBLE PRECISION,
        roe DOUBLE PRECISION,
        gross_margin DOUBLE PRECISION,
        net_margin DOUBLE PRECISION,
        debt_ratio DOUBLE PRECISION,
        current_ratio DOUBLE PRECISION,
        revenue_yoy DOUBLE PRECISION,
        net_income_yoy DOUBLE PRECISION,
        roe_yoy DOUBLE PRECISION,
        ocf_to_profit DOUBLE PRECISION,
        computed_at TEXT NOT NULL,
        PRIMARY KEY (ts_code, end_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.financial_sync_meta (
        ts_code TEXT PRIMARY KEY,
        last_sync_at TEXT NOT NULL,
        latest_end_date TEXT NOT NULL DEFAULT '',
        latest_ann_date TEXT NOT NULL DEFAULT '',
        sync_status TEXT NOT NULL DEFAULT 'ok',
        error_message TEXT NOT NULL DEFAULT '',
        periods_count INTEGER NOT NULL DEFAULT 0,
        last_access_at TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.valuation_history (
        ts_code TEXT NOT NULL,
        trade_date TEXT NOT NULL,
        close DOUBLE PRECISION,
        pe_ttm DOUBLE PRECISION,
        pb DOUBLE PRECISION,
        total_mv DOUBLE PRECISION,
        circ_mv DOUBLE PRECISION,
        turnover_rate DOUBLE PRECISION,
        fetched_at TEXT NOT NULL,
        PRIMARY KEY (ts_code, trade_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_valuation_history_ts_date ON app.valuation_history(ts_code, trade_date DESC)",
    """
    CREATE TABLE IF NOT EXISTS app.disclosure_calendar (
        ts_code TEXT NOT NULL,
        end_date TEXT NOT NULL,
        pre_date TEXT NOT NULL DEFAULT '',
        ann_date TEXT NOT NULL DEFAULT '',
        actual_date TEXT NOT NULL DEFAULT '',
        fetched_at TEXT NOT NULL,
        PRIMARY KEY (ts_code, end_date)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.symbol_suspend_days (
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        cal_date TEXT NOT NULL,
        suspend_type TEXT NOT NULL DEFAULT 'S',
        PRIMARY KEY (symbol, exchange, cal_date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_symbol_suspend_lookup ON app.symbol_suspend_days(symbol, exchange, cal_date)",
    """
    CREATE TABLE IF NOT EXISTS app.stock_note_memos (
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        body TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL,
        PRIMARY KEY (symbol, exchange)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.stock_note_entries (
        id BIGSERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        body TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_stock_note_entries_lookup ON app.stock_note_entries(symbol, exchange, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS app.stock_analysis_reports (
        id BIGSERIAL PRIMARY KEY,
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        body TEXT NOT NULL,
        source_scope TEXT NOT NULL DEFAULT '',
        context_json TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_stock_analysis_reports_lookup ON app.stock_analysis_reports(symbol, exchange, created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS app.screener_schemes (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        config_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.screener_recipes (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL UNIQUE,
        trigger_kind TEXT NOT NULL,
        config_json TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.screener_runs (
        id TEXT PRIMARY KEY,
        condition TEXT NOT NULL,
        source TEXT NOT NULL,
        row_count INTEGER NOT NULL,
        total_scanned INTEGER NOT NULL DEFAULT 0,
        config_json TEXT NOT NULL DEFAULT '{}',
        result_json TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_screener_runs_created ON app.screener_runs(created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS app.backtest_runs (
        id TEXT PRIMARY KEY,
        vt_symbol TEXT NOT NULL,
        strategy TEXT NOT NULL,
        interval TEXT NOT NULL DEFAULT 'd',
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        total_return DOUBLE PRECISION,
        max_drawdown DOUBLE PRECISION,
        sharpe_ratio DOUBLE PRECISION,
        trade_count INTEGER,
        source TEXT NOT NULL DEFAULT 'single',
        batch_id TEXT,
        raw_statistics_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_backtest_runs_created ON app.backtest_runs(created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS app.sector_flow_daily (
        trade_date TEXT NOT NULL,
        sector_kind TEXT NOT NULL,
        sector_id TEXT NOT NULL,
        name TEXT NOT NULL,
        change_pct DOUBLE PRECISION NOT NULL,
        net_flow_yi DOUBLE PRECISION NOT NULL,
        flow_source TEXT NOT NULL DEFAULT '',
        PRIMARY KEY (trade_date, sector_kind, sector_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sector_flow_daily_lookup ON app.sector_flow_daily(sector_kind, sector_id, trade_date DESC)",
    """
    CREATE TABLE IF NOT EXISTS app.sector_flow_intraday (
        trade_date TEXT NOT NULL,
        sector_kind TEXT NOT NULL,
        sector_id TEXT NOT NULL,
        name TEXT NOT NULL,
        bucket_time TEXT NOT NULL,
        clock_minutes INTEGER NOT NULL,
        net_flow_yi DOUBLE PRECISION NOT NULL,
        change_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
        PRIMARY KEY (trade_date, sector_kind, sector_id, bucket_time)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sector_flow_intraday_lookup ON app.sector_flow_intraday(trade_date, sector_kind, clock_minutes)",
    """
    CREATE TABLE IF NOT EXISTS app.notify_delivery_log (
        id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        channel TEXT NOT NULL DEFAULT 'feishu',
        payload_json TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL,
        error TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_notify_delivery_log_created ON app.notify_delivery_log(created_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS app.trading_plans (
        id TEXT PRIMARY KEY,
        trade_date TEXT NOT NULL,
        emotion_expected TEXT NOT NULL DEFAULT '',
        max_position_pct DOUBLE PRECISION NOT NULL DEFAULT 0,
        notes TEXT NOT NULL DEFAULT '',
        status TEXT NOT NULL DEFAULT 'draft',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_trading_plans_trade_date ON app.trading_plans(trade_date DESC, status)",
    """
    CREATE TABLE IF NOT EXISTS app.trading_plan_symbols (
        plan_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL,
        allowed_modes TEXT NOT NULL DEFAULT '',
        entry_conditions TEXT NOT NULL DEFAULT '',
        exit_conditions TEXT NOT NULL DEFAULT '',
        sort_order INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (plan_id, symbol, exchange),
        FOREIGN KEY (plan_id) REFERENCES app.trading_plans(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.emotion_limit_ladder_daily (
        trade_date TEXT PRIMARY KEY,
        max_limit_times INTEGER NOT NULL DEFAULT 0,
        max_board_vt_symbol TEXT NOT NULL DEFAULT '',
        linked_board_vt_symbols TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.trading_playbook_sections (
        section_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        body_md TEXT NOT NULL DEFAULT '',
        collapsed INTEGER NOT NULL DEFAULT 0,
        sort_order INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.trading_playbook_discipline_daily (
        trade_date TEXT NOT NULL,
        check_id TEXT NOT NULL,
        checked INTEGER NOT NULL DEFAULT 0,
        PRIMARY KEY (trade_date, check_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.feed_subscriptions (
        id TEXT PRIMARY KEY,
        source_type TEXT NOT NULL DEFAULT 'bilibili_up',
        source_id TEXT NOT NULL,
        display_name TEXT NOT NULL DEFAULT '',
        avatar_url TEXT NOT NULL DEFAULT '',
        config_json TEXT NOT NULL DEFAULT '{}',
        enabled INTEGER NOT NULL DEFAULT 1,
        sort_order INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(source_type, source_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS app.feed_items (
        id TEXT PRIMARY KEY,
        subscription_id TEXT NOT NULL,
        source_type TEXT NOT NULL,
        external_id TEXT NOT NULL,
        item_type TEXT NOT NULL,
        title TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        url TEXT NOT NULL,
        author_name TEXT NOT NULL DEFAULT '',
        published_at TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '{}',
        read_at TEXT,
        created_at TEXT NOT NULL,
        UNIQUE(source_type, external_id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_feed_items_published ON app.feed_items(published_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_feed_items_sub ON app.feed_items(subscription_id, published_at DESC)",
    """
    CREATE TABLE IF NOT EXISTS app.feed_cursors (
        subscription_id TEXT PRIMARY KEY,
        last_video_ts INTEGER NOT NULL DEFAULT 0,
        last_dynamic_id TEXT NOT NULL DEFAULT '',
        last_ok_at TEXT,
        last_error TEXT NOT NULL DEFAULT ''
    )
    """,
)

CHAT_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS chat.sessions (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL DEFAULT '',
        scene TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS chat.messages (
        id BIGSERIAL PRIMARY KEY,
        session_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (session_id) REFERENCES chat.sessions(id)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_messages_session ON chat.messages(session_id, id)",
    """
    CREATE TABLE IF NOT EXISTS chat.llm_turn_traces (
        turn_id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        turn_index INTEGER NOT NULL,
        user_text TEXT NOT NULL,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        trace_json TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_llm_turn_traces_session ON chat.llm_turn_traces(session_id, turn_index)",
    """
    CREATE TABLE IF NOT EXISTS chat.llm_tool_calls (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        tool_name TEXT NOT NULL,
        arguments_json TEXT NOT NULL DEFAULT '{}',
        result_preview TEXT NOT NULL DEFAULT '',
        success INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_llm_tool_calls_created ON chat.llm_tool_calls(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_llm_tool_calls_session ON chat.llm_tool_calls(session_id)",
)

AUTH_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS auth.users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        username TEXT UNIQUE NOT NULL,
        display_name TEXT NOT NULL DEFAULT '',
        password_hash TEXT NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS auth.user_preferences (
        user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
        namespace TEXT NOT NULL,
        key TEXT NOT NULL,
        value_json JSONB NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        PRIMARY KEY (user_id, namespace, key)
    )
    """,
)

SYSTEM_TABLES = (
    """
    CREATE TABLE IF NOT EXISTS system.scheduler_config (
        id TEXT PRIMARY KEY DEFAULT 'default',
        config_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
    )
    """,
)

ALL_STATEMENTS = (*SCHEMAS, *APP_TABLES, *CHAT_TABLES, *AUTH_TABLES, *SYSTEM_TABLES)

DOWNGRADE_STATEMENTS = (
    "DROP SCHEMA IF EXISTS cache CASCADE",
    "DROP SCHEMA IF EXISTS chat CASCADE",
    "DROP SCHEMA IF EXISTS app CASCADE",
    "DROP SCHEMA IF EXISTS auth CASCADE",
    "DROP SCHEMA IF EXISTS system CASCADE",
)
