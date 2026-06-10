"""行情页配置：市场 / 自选 / 本地。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MAX_DISPLAY_ROWS = 300
MARKET_PAGE_SIZE = 50
SEARCH_DEBOUNCE_MS = 300
STREAM_QUOTE_DEBOUNCE_MS = 150
AI_CONTEXT_DEBOUNCE_MS = 500
STATS_DEBOUNCE_MS = 500
SCHEDULER_UI_FALLBACK_REFRESH_MS = 60_000
MARKET_QUOTE_REFRESH_MS = 15000
WATCHLIST_QUOTE_REFRESH_MS = 3000
# 兼容旧引用
QUOTE_REFRESH_MS = MARKET_QUOTE_REFRESH_MS


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
) -> str:
    if not auto_refresh:
        return "行情不自动刷新"
    seconds = quote_refresh_seconds(refresh_ms)
    if quote_source == "market":
        return f"行情每 {seconds} 秒自动刷新（Redis）"
    if quote_source == "watchlist":
        return f"行情/五档 WebSocket，图表每 {seconds} 秒刷新"
    return f"行情每 {seconds} 秒自动刷新"


from vnpy_ashare.ui.quotes.quote_columns import LOCAL_TABLE_HEADERS, quote_table_headers

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
    market_page_size: int = MARKET_PAGE_SIZE
    table_header_sortable: bool = False
    show_watchlist_move_buttons: bool = False
    show_backtest_button: bool = True
    show_batch_backtest_button: bool = False
    show_diagnose_button: bool = False
    show_diagnose_panel: bool = False
    show_kline: bool = True
    show_board_filter: bool = False
    hide_quote_header: bool = False
    column_configurable: bool = False
    search_max_width: int = 280


DEFAULT_WATCHLIST_COLUMNS: list[str] = [
    "symbol",
    "name",
    "last_price",
    "change_pct",
    "change_amount",
    "amplitude",
    "volume",
    "amount",
    "high_price",
    "low_price",
    "trade_time",
]

MARKET_VISIBLE_COLUMNS: list[str] = [
    "symbol",
    "name",
    "last_price",
    "change_pct",
    "change_amount",
    "volume",
    "amount",
    "turnover_rate",
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
        search_placeholder="输入代码 / 名称搜索 A 股",
        search_max_width=320,
        show_sync_button=True,
        show_download_button=True,
        show_local_column=True,
        require_keyword=False,
        show_add_watchlist_button=True,
        use_market_rank=True,
        market_page_size=MARKET_PAGE_SIZE,
        table_header_sortable=True,
        quote_refresh_ms=MARKET_QUOTE_REFRESH_MS,
        quote_source="market",
        quote_refresh_source="watchlist",  # auto-refresh 直连 TickFlow 实时行情
        show_kline=False,
        show_board_filter=True,
        hide_quote_header=True,
    ),
    "自选": PageConfig(
        title="自选",
        scope_key="自选池",
        search_placeholder="搜索自选池代码 / 名称",
        search_max_width=240,
        show_sync_button=False,
        show_download_button=True,
        show_local_column=True,
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
        show_run_output_panel=True,
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
        show_local_column=False,
        require_keyword=False,
        auto_refresh_quotes=False,
        show_diagnose_button=True,
        show_diagnose_panel=False,
    ),
}
