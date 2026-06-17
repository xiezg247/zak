"""雷达卡片内置默认（与 QSettings 覆盖层解耦，避免 catalog ↔ prefs 循环）。"""

from __future__ import annotations

# 自动刷新时每隔 N 次做一次全量重算（其余仅更新现价 / 涨幅）
RADAR_FULL_REFRESH_EVERY: dict[str, int] = {
    "discovery_volume_surge": 5,
    "discovery_moneyflow_intraday": 5,
    "discovery_limit_ladder": 5,
    "discovery_first_board": 5,
    "watchlist_intraday": 5,
    "sector_theme": 3,
}
