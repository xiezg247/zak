"""行情榜单元数据注册表。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel
from vnpy_ashare.quotes.market.market_breadth import LIMIT_DOWN_PCT, LIMIT_UP_PCT

NEAR_LIMIT_UP_MIN = 7.0

RANK_GROUP_PRICE = "价格"
RANK_GROUP_VOLUME = "量能"
RANK_GROUP_FUND = "资金"
RANK_GROUP_PERSONAL = "我的"

RankScope = Literal["all", "watchlist"]


class RankFilter(FrozenModel):
    field: str = Field(description="过滤字段名")
    min_value: float | None = Field(default=None, description="最小值阈值")
    max_value: float | None = Field(default=None, description="最大值阈值")
    min_inclusive: bool = Field(default=True, description="最小值是否含边界")
    max_inclusive: bool = Field(default=True, description="最大值是否含边界")


class RankDefinition(FrozenModel):
    """单榜定义：Redis ZSET 字段、排序方向、可选过滤与分组。"""

    id: str = Field(description="榜单唯一标识")
    title: str = Field(description="榜单展示标题")
    redis_field: str = Field(description="Redis ZSET 排序字段")
    ascending: bool = Field(default=False, description="是否升序排列")
    sort_column: str = Field(default="", description="表格排序列名")
    filter: RankFilter | None = Field(default=None, description="可选数值过滤条件")
    group: str = Field(default=RANK_GROUP_PRICE, description="侧栏分组名称")
    require_open_below_prev: bool = Field(default=False, description="要求低开（开盘价低于昨收）")
    require_open_above_prev: bool = Field(default=False, description="要求高开（开盘价高于昨收）")
    require_intraday_rise: bool = Field(default=False, description="要求日内上涨")
    require_intraday_fall: bool = Field(default=False, description="要求日内下跌")
    scope: RankScope = Field(default="all", description="榜单范围：全市场或自选")


DEFAULT_RANK_ID = "change_pct"


def _rank_filter(field: str, **kwargs: Any) -> RankFilter:
    return RankFilter(field=field, **kwargs)


def _rank(
    id: str,
    title: str,
    redis_field: str,
    ascending: bool = False,
    sort_column: str = "",
    **kwargs: Any,
) -> RankDefinition:
    return RankDefinition(
        id=id,
        title=title,
        redis_field=redis_field,
        ascending=ascending,
        sort_column=sort_column or redis_field,
        **kwargs,
    )


RANK_DEFINITIONS: tuple[RankDefinition, ...] = (
    _rank("change_pct", "涨幅榜", "change_pct", group=RANK_GROUP_PRICE),
    _rank("change_pct_asc", "跌幅榜", "change_pct", ascending=True, group=RANK_GROUP_PRICE),
    _rank(
        "limit_up",
        "涨停",
        "change_pct",
        filter=_rank_filter("change_pct", min_value=LIMIT_UP_PCT),
        group=RANK_GROUP_PRICE,
    ),
    _rank(
        "limit_times",
        "连板榜",
        "limit_times",
        sort_column="limit_times",
        filter=_rank_filter("limit_times", min_value=1, min_inclusive=True),
        group=RANK_GROUP_PRICE,
    ),
    _rank(
        "limit_down",
        "跌停",
        "change_pct",
        ascending=True,
        filter=_rank_filter("change_pct", max_value=LIMIT_DOWN_PCT),
        group=RANK_GROUP_PRICE,
    ),
    _rank(
        "near_limit_up",
        "临停",
        "change_pct",
        filter=_rank_filter(
            "change_pct",
            min_value=NEAR_LIMIT_UP_MIN,
            max_value=LIMIT_UP_PCT,
            max_inclusive=False,
        ),
        group=RANK_GROUP_PRICE,
    ),
    _rank(
        "change_speed_5m",
        "涨速",
        "change_speed_5m",
        sort_column="change_speed_5m",
        filter=_rank_filter("change_speed_5m", min_value=0, min_inclusive=False),
        group=RANK_GROUP_PRICE,
    ),
    _rank(
        "gap_up_rally",
        "低开高走",
        "intraday_change_pct",
        sort_column="intraday_change_pct",
        require_open_below_prev=True,
        require_intraday_rise=True,
        group=RANK_GROUP_PRICE,
    ),
    _rank(
        "gap_down_fade",
        "高开低走",
        "intraday_change_pct",
        ascending=True,
        sort_column="intraday_change_pct",
        require_open_above_prev=True,
        require_intraday_fall=True,
        group=RANK_GROUP_PRICE,
    ),
    _rank(
        "volume_ratio",
        "量比榜",
        "volume_ratio",
        sort_column="volume_ratio",
        filter=_rank_filter("volume_ratio", min_value=0, min_inclusive=False),
        group=RANK_GROUP_VOLUME,
    ),
    _rank("turnover_rate", "换手榜", "turnover_rate", group=RANK_GROUP_VOLUME),
    _rank("amount", "成交额", "amount", group=RANK_GROUP_VOLUME),
    _rank("volume", "成交量", "volume", group=RANK_GROUP_VOLUME),
    _rank("amplitude", "振幅榜", "amplitude", group=RANK_GROUP_VOLUME),
    _rank(
        "net_mf_in",
        "主力净流入",
        "net_mf_amount",
        sort_column="net_mf_amount",
        filter=_rank_filter("net_mf_amount", min_value=0, min_inclusive=False),
        group=RANK_GROUP_FUND,
    ),
    _rank(
        "net_mf_out",
        "主力净流出",
        "net_mf_amount",
        ascending=True,
        sort_column="net_mf_amount",
        filter=_rank_filter("net_mf_amount", max_value=0, max_inclusive=False),
        group=RANK_GROUP_FUND,
    ),
    _rank(
        "watchlist_change_pct",
        "自选涨幅",
        "change_pct",
        scope="watchlist",
        group=RANK_GROUP_PERSONAL,
    ),
    _rank(
        "watchlist_change_speed_5m",
        "自选涨速",
        "change_speed_5m",
        sort_column="change_speed_5m",
        filter=_rank_filter("change_speed_5m", min_value=0, min_inclusive=False),
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
