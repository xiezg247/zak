"""行情榜单元数据注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vnpy_ashare.quotes.market.market_breadth import LIMIT_DOWN_PCT, LIMIT_UP_PCT

NEAR_LIMIT_UP_MIN = 7.0

RANK_GROUP_PRICE = "价格"
RANK_GROUP_VOLUME = "量能"
RANK_GROUP_FUND = "资金"
RANK_GROUP_PERSONAL = "我的"

RankScope = Literal["all", "watchlist"]


@dataclass(frozen=True)
class RankFilter:
    field: str
    min_value: float | None = None
    max_value: float | None = None
    min_inclusive: bool = True
    max_inclusive: bool = True


@dataclass(frozen=True)
class RankDefinition:
    """单榜定义：Redis ZSET 字段、排序方向、可选过滤与分组。"""

    id: str
    title: str
    redis_field: str
    ascending: bool = False
    sort_column: str = ""
    filter: RankFilter | None = None
    group: str = RANK_GROUP_PRICE
    require_open_below_prev: bool = False
    require_open_above_prev: bool = False
    require_intraday_rise: bool = False
    require_intraday_fall: bool = False
    scope: RankScope = "all"


DEFAULT_RANK_ID = "change_pct"

RANK_DEFINITIONS: tuple[RankDefinition, ...] = (
    RankDefinition("change_pct", "涨幅榜", "change_pct", False, "change_pct", group=RANK_GROUP_PRICE),
    RankDefinition("change_pct_asc", "跌幅榜", "change_pct", True, "change_pct", group=RANK_GROUP_PRICE),
    RankDefinition(
        "limit_up",
        "涨停",
        "change_pct",
        False,
        "change_pct",
        filter=RankFilter("change_pct", min_value=LIMIT_UP_PCT),
        group=RANK_GROUP_PRICE,
    ),
    RankDefinition(
        "limit_times",
        "连板榜",
        "limit_times",
        False,
        "limit_times",
        filter=RankFilter("limit_times", min_value=1, min_inclusive=True),
        group=RANK_GROUP_PRICE,
    ),
    RankDefinition(
        "limit_down",
        "跌停",
        "change_pct",
        True,
        "change_pct",
        filter=RankFilter("change_pct", max_value=LIMIT_DOWN_PCT),
        group=RANK_GROUP_PRICE,
    ),
    RankDefinition(
        "near_limit_up",
        "临停",
        "change_pct",
        False,
        "change_pct",
        filter=RankFilter(
            "change_pct",
            min_value=NEAR_LIMIT_UP_MIN,
            max_value=LIMIT_UP_PCT,
            max_inclusive=False,
        ),
        group=RANK_GROUP_PRICE,
    ),
    RankDefinition(
        "change_speed_5m",
        "涨速",
        "change_speed_5m",
        False,
        "change_speed_5m",
        filter=RankFilter("change_speed_5m", min_value=0, min_inclusive=False),
        group=RANK_GROUP_PRICE,
    ),
    RankDefinition(
        "gap_up_rally",
        "低开高走",
        "intraday_change_pct",
        False,
        "intraday_change_pct",
        require_open_below_prev=True,
        require_intraday_rise=True,
        group=RANK_GROUP_PRICE,
    ),
    RankDefinition(
        "gap_down_fade",
        "高开低走",
        "intraday_change_pct",
        True,
        "intraday_change_pct",
        require_open_above_prev=True,
        require_intraday_fall=True,
        group=RANK_GROUP_PRICE,
    ),
    RankDefinition(
        "volume_ratio",
        "量比榜",
        "volume_ratio",
        False,
        "volume_ratio",
        filter=RankFilter("volume_ratio", min_value=0, min_inclusive=False),
        group=RANK_GROUP_VOLUME,
    ),
    RankDefinition("turnover_rate", "换手榜", "turnover_rate", False, "turnover_rate", group=RANK_GROUP_VOLUME),
    RankDefinition("amount", "成交额", "amount", False, "amount", group=RANK_GROUP_VOLUME),
    RankDefinition("volume", "成交量", "volume", False, "volume", group=RANK_GROUP_VOLUME),
    RankDefinition("amplitude", "振幅榜", "amplitude", False, "amplitude", group=RANK_GROUP_VOLUME),
    RankDefinition(
        "net_mf_in",
        "主力净流入",
        "net_mf_amount",
        False,
        "net_mf_amount",
        filter=RankFilter("net_mf_amount", min_value=0, min_inclusive=False),
        group=RANK_GROUP_FUND,
    ),
    RankDefinition(
        "net_mf_out",
        "主力净流出",
        "net_mf_amount",
        True,
        "net_mf_amount",
        filter=RankFilter("net_mf_amount", max_value=0, max_inclusive=False),
        group=RANK_GROUP_FUND,
    ),
    RankDefinition(
        "watchlist_change_pct",
        "自选涨幅",
        "change_pct",
        False,
        "change_pct",
        scope="watchlist",
        group=RANK_GROUP_PERSONAL,
    ),
    RankDefinition(
        "watchlist_change_speed_5m",
        "自选涨速",
        "change_speed_5m",
        False,
        "change_speed_5m",
        filter=RankFilter("change_speed_5m", min_value=0, min_inclusive=False),
        scope="watchlist",
        group=RANK_GROUP_PERSONAL,
    ),
)

_RANK_BY_ID: dict[str, RankDefinition] = {spec.id: spec for spec in RANK_DEFINITIONS}


def list_rank_definitions() -> tuple[RankDefinition, ...]:
    return RANK_DEFINITIONS


def list_rank_groups() -> tuple[str, ...]:
    groups: list[str] = []
    for spec in RANK_DEFINITIONS:
        if spec.group not in groups:
            groups.append(spec.group)
    return tuple(groups)


def ranks_in_group(group: str) -> tuple[RankDefinition, ...]:
    return tuple(spec for spec in RANK_DEFINITIONS if spec.group == group)


def get_rank_definition(rank_id: str) -> RankDefinition:
    return _RANK_BY_ID.get(rank_id) or _RANK_BY_ID[DEFAULT_RANK_ID]


def rank_definition_row(rank_id: str) -> int:
    """侧栏 QListWidget 中可选项的行号（含不可选分组标题）。"""
    row = 0
    seen_groups: set[str] = set()
    for spec in RANK_DEFINITIONS:
        if spec.group not in seen_groups:
            seen_groups.add(spec.group)
            row += 1
        if spec.id == rank_id:
            return row
        row += 1
    return 0


def iter_rank_sidebar_rows() -> tuple[tuple[str, RankDefinition | None], ...]:
    """侧栏行：(分组标题, None) 或 ("", spec)。"""
    rows: list[tuple[str, RankDefinition | None]] = []
    seen: set[str] = set()
    for spec in RANK_DEFINITIONS:
        if spec.group not in seen:
            seen.add(spec.group)
            rows.append((spec.group, None))
        rows.append(("", spec))
    return tuple(rows)


def rank_definition_index(rank_id: str) -> int:
    return rank_definition_row(rank_id)
