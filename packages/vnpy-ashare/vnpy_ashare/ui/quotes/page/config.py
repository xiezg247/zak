"""行情页配置：市场 / 自选 / 本地。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.ui.quotes.table.columns import LOCAL_TABLE_HEADERS, quote_table_headers

MAX_DISPLAY_ROWS = 300
LOCAL_PAGE_SIZE = 50
MARKET_PAGE_SIZE = 100
MARKET_SCROLL_DEBOUNCE_MS = 180
MARKET_SCROLL_LOAD_COOLDOWN_MS = 500
MARKET_SCROLL_REFRESH_VISIBLE_BUFFER = 8
SEARCH_DEBOUNCE_MS = 450
STREAM_QUOTE_DEBOUNCE_MS = 150
STREAM_CHART_QUOTE_DEBOUNCE_MS = 100
AI_CONTEXT_DEBOUNCE_MS = 500
STATS_DEBOUNCE_MS = 500
SCHEDULER_UI_FALLBACK_REFRESH_MS = 60_000
MARKET_LIVE_DISPLAY_LIMIT = 100
MARKET_QUOTE_REFRESH_MS = 15000
WATCHLIST_QUOTE_REFRESH_MS = 3000
WATCHLIST_SIGNAL_REFRESH_MS = 300_000
MARKET_AUTO_REFRESH_DEFAULT = True
MARKET_AUTO_REFRESH_SETTINGS_KEY = "quotes/market/auto_refresh_v2"
RADAR_CARD_REFRESH_SETTINGS_PREFIX = "quotes/radar/card_refresh"
RADAR_MANUAL_REFRESH_HINT = "↻ 全量刷新，下拉可选「仅更新行情」；统计区异动卡可设自动刷新；展望区读缓存，非确定性预测"


def radar_refresh_hint() -> str:
    from vnpy_ashare.domain.market_hours import ashare_market_phase_label, is_ashare_trading_session

    phase = ashare_market_phase_label()
    auto_part = "异动卡按设定周期刷新" if is_ashare_trading_session() else "异动卡暂停自动刷新"
    return f"当前{phase} · {auto_part}；{RADAR_MANUAL_REFRESH_HINT}"


def _coerce_settings_int(value: object, *, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    if isinstance(value, float):
        return int(value)
    return default


def load_radar_card_refresh_ms(card_id: str, default_ms: int | None) -> int:
    settings = get_settings()
    key = f"{RADAR_CARD_REFRESH_SETTINGS_PREFIX}/{card_id}"
    fallback = int(default_ms or 0)
    return _coerce_settings_int(settings.value(key), default=fallback)


def save_radar_card_refresh_ms(card_id: str, ms: int) -> None:
    settings = get_settings()
    key = f"{RADAR_CARD_REFRESH_SETTINGS_PREFIX}/{card_id}"
    settings.setValue(key, int(ms))


def _coerce_settings_bool(value: object, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def load_market_auto_refresh_pref() -> bool:
    settings = get_settings()
    return _coerce_settings_bool(
        settings.value(MARKET_AUTO_REFRESH_SETTINGS_KEY),
        default=MARKET_AUTO_REFRESH_DEFAULT,
    )


def save_market_auto_refresh_pref(enabled: bool) -> None:
    settings = get_settings()
    settings.setValue(MARKET_AUTO_REFRESH_SETTINGS_KEY, enabled)


def quote_refresh_seconds(refresh_ms: int) -> int:
    return max(refresh_ms // 1000, 1)


def quote_source_label(
    config: PageConfig,
    *,
    stream_active: bool = False,
    gateway_active: bool = False,
) -> str:
    """状态栏行情源文案（TickFlow / Redis；P4 后含 Gateway）。"""
    if gateway_active:
        return "行情源：Gateway"
    if config.use_local_table:
        return "行情源：本地 K 线"
    if not config.quote_source:
        return ""
    if config.use_quote_stream:
        if stream_active:
            return "行情源：TickFlow (WebSocket)"
        return "行情源：TickFlow"
    refresh_src = config.quote_refresh_source or config.quote_source
    if config.quote_source == "market" and refresh_src == "watchlist":
        return "行情源：Redis + TickFlow"
    if config.quote_source == "market":
        return "行情源：Redis"
    return "行情源：TickFlow"


def quote_refresh_hint(
    *,
    auto_refresh: bool,
    refresh_ms: int,
    quote_source: Literal["market", "watchlist"] | None = None,
    paused_for_hours: bool = False,
) -> str:
    if not auto_refresh:
        return "行情不自动刷新"
    if paused_for_hours:
        return "非交易时段，行情暂停自动刷新"
    seconds = quote_refresh_seconds(refresh_ms)
    if quote_source == "market":
        return f"行情每 {seconds} 秒自动刷新（Redis，交易时段）"
    if quote_source == "watchlist":
        return f"行情/五档 WebSocket，图表每 {seconds} 秒刷新（交易时段）"
    return f"行情每 {seconds} 秒自动刷新（交易时段）"


TABLE_HEADERS_WITH_LOCAL = quote_table_headers(tail_header="本地")
TABLE_HEADERS_LOCAL = LOCAL_TABLE_HEADERS


@dataclass(frozen=True)
class PageConfig:
    title: str
    scope_key: str
    search_placeholder: str
    show_sync_button: bool
    show_download_button: bool
    show_local_column: bool
    require_keyword: bool
    show_fill_button: bool = False
    show_redownload_button: bool = False
    show_delete_button: bool = False
    show_run_output_panel: bool = False
    show_batch_fill_button: bool = False
    show_batch_gap_fill_button: bool = False
    use_local_table: bool = False
    use_local_pagination: bool = False
    local_page_size: int = LOCAL_PAGE_SIZE
    show_add_watchlist_button: bool = False
    show_remove_watchlist_button: bool = False
    auto_refresh_quotes: bool = True
    quote_refresh_ms: int = MARKET_QUOTE_REFRESH_MS
    quote_source: Literal["market", "watchlist"] | None = None
    quote_refresh_source: Literal["market", "watchlist"] | None = None  # auto-refresh 数据源（None=同 quote_source）
    show_depth_panel: bool = False
    show_chart_tabs: bool = False
    use_quote_stream: bool = False
    use_market_rank: bool = False
    market_full_list: bool = False
    market_scroll_paging: bool = False
    market_page_size: int = MARKET_PAGE_SIZE
    market_live_display_limit: int = MARKET_LIVE_DISPLAY_LIMIT
    table_header_sortable: bool = False
    show_watchlist_move_buttons: bool = False
    show_refresh_quotes_button: bool = False
    show_backtest_button: bool = True
    show_batch_backtest_button: bool = False
    show_diagnose_button: bool = False
    show_diagnose_panel: bool = False
    show_kline: bool = True
    show_board_filter: bool = False
    show_industry_filter: bool = False
    hide_quote_header: bool = False
    column_configurable: bool = False
    show_rank_sidebar: bool = False
    use_radar_cards: bool = False
    default_rank_id: str = "change_pct"
    show_watchlist_signals: bool = False
    show_watchlist_positions: bool = False
    show_stock_notes: bool = False
    show_watchlist_multiview: bool = False
    show_watchlist_groups: bool = False
    search_max_width: int = 280


DEFAULT_WATCHLIST_COLUMNS: list[str] = [
    "symbol",
    "name",
    "industry",
    "last_price",
    "change_pct",
    "change_amount",
    "amplitude",
    "volume",
    "amount",
    "turnover_rate",
    "volume_ratio",
    "net_mf_amount",
    "high_price",
    "low_price",
    "trade_time",
]

INDUSTRY_BOARD_COLUMN_KEYS: tuple[str, ...] = ("industry", "market_board")


def ensure_columns_from_template(
    columns: list[str],
    template: list[str],
    *,
    available_keys: set[str],
) -> list[str]:
    """按模板顺序补全缺失列（不改变已有列的相对顺序）。"""
    result = list(columns)
    for key in template:
        if key not in available_keys or key in result:
            continue
        insert_at = len(result)
        key_idx = template.index(key)
        for i in range(key_idx - 1, -1, -1):
            prev = template[i]
            if prev in result:
                insert_at = result.index(prev) + 1
                break
        else:
            if "name" in result:
                insert_at = result.index("name") + 1
        result.insert(insert_at, key)
    return result


def ensure_industry_board_columns(columns: list[str], *, available_keys: set[str]) -> list[str]:
    """确保行业 / 板块列出现在证券名称之后（市场页）。"""
    return ensure_columns_from_template(
        columns,
        list(INDUSTRY_BOARD_COLUMN_KEYS),
        available_keys=available_keys,
    )


MARKET_VISIBLE_COLUMNS: list[str] = [
    "symbol",
    "name",
    "industry",
    "market_board",
    "last_price",
    "change_pct",
    "limit_times",
    "change_speed_5m",
    "change_amount",
    "volume",
    "amount",
    "turnover_rate",
    "volume_ratio",
    "net_mf_amount",
    "amplitude",
    "trade_time",
]

ALL_TAIL_COLUMNS: dict[str, str] = {
    "local": "本地",
    "start": "起始",
    "end": "结束",
    "count": "K线数",
    "status": "状态",
}


PAGE_CONFIGS: dict[str, PageConfig] = {
    "市场": PageConfig(
        title="市场",
        scope_key="全部A股",
        search_placeholder="输入代码 / 名称搜索（不含行业）",
        search_max_width=320,
        show_sync_button=True,
        show_download_button=True,
        show_local_column=False,
        require_keyword=False,
        show_add_watchlist_button=True,
        use_market_rank=True,
        market_full_list=True,
        market_scroll_paging=False,
        market_page_size=MARKET_PAGE_SIZE,
        market_live_display_limit=MARKET_LIVE_DISPLAY_LIMIT,
        table_header_sortable=True,
        auto_refresh_quotes=MARKET_AUTO_REFRESH_DEFAULT,
        quote_refresh_ms=MARKET_QUOTE_REFRESH_MS,
        quote_source="market",
        quote_refresh_source="market",
        show_kline=False,
        show_board_filter=True,
        show_industry_filter=True,
        hide_quote_header=True,
        show_rank_sidebar=True,
    ),
    "雷达": PageConfig(
        title="雷达",
        scope_key="洞察",
        search_placeholder="",
        search_max_width=0,
        show_sync_button=False,
        show_download_button=False,
        show_local_column=False,
        require_keyword=False,
        show_add_watchlist_button=False,
        auto_refresh_quotes=False,
        quote_source="market",
        quote_refresh_source="market",
        show_kline=False,
        show_board_filter=False,
        hide_quote_header=True,
        use_radar_cards=True,
    ),
    "自选": PageConfig(
        title="自选",
        scope_key="自选池",
        search_placeholder="搜索自选池代码 / 名称",
        search_max_width=240,
        show_sync_button=False,
        show_download_button=True,
        show_local_column=False,
        require_keyword=False,
        show_remove_watchlist_button=True,
        show_watchlist_move_buttons=True,
        quote_refresh_ms=WATCHLIST_QUOTE_REFRESH_MS,
        quote_source="watchlist",
        show_depth_panel=True,
        show_chart_tabs=True,
        use_quote_stream=True,
        column_configurable=True,
        show_diagnose_button=True,
        show_diagnose_panel=False,
        show_batch_backtest_button=True,
        show_refresh_quotes_button=True,
        show_run_output_panel=False,
        show_watchlist_signals=True,
        show_watchlist_positions=True,
        show_stock_notes=True,
        show_watchlist_multiview=True,
        show_watchlist_groups=True,
    ),
    "本地": PageConfig(
        title="本地",
        scope_key="已下载",
        search_placeholder="搜索本地已下载标的",
        search_max_width=260,
        show_sync_button=False,
        show_download_button=False,
        show_fill_button=True,
        show_redownload_button=True,
        show_delete_button=True,
        show_run_output_panel=True,
        show_batch_fill_button=True,
        show_batch_gap_fill_button=True,
        use_local_table=True,
        use_local_pagination=True,
        local_page_size=LOCAL_PAGE_SIZE,
        show_local_column=False,
        require_keyword=False,
        auto_refresh_quotes=False,
        show_diagnose_button=True,
        show_diagnose_panel=False,
    ),
}
