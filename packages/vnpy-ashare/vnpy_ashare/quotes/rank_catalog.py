"""行情榜单元数据注册表。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RankDefinition:
    """单榜定义：Redis ZSET 字段、排序方向与表格列。"""

    id: str
    title: str
    redis_field: str
    ascending: bool = False
    sort_column: str = ""


DEFAULT_RANK_ID = "change_pct"

RANK_DEFINITIONS: tuple[RankDefinition, ...] = (
    RankDefinition("change_pct", "涨幅榜", "change_pct", False, "change_pct"),
    RankDefinition("change_pct_asc", "跌幅榜", "change_pct", True, "change_pct"),
    RankDefinition("turnover_rate", "换手榜", "turnover_rate", False, "turnover_rate"),
    RankDefinition("amount", "成交额", "amount", False, "amount"),
    RankDefinition("volume", "成交量", "volume", False, "volume"),
    RankDefinition("amplitude", "振幅榜", "amplitude", False, "amplitude"),
)

_RANK_BY_ID: dict[str, RankDefinition] = {spec.id: spec for spec in RANK_DEFINITIONS}


def list_rank_definitions() -> tuple[RankDefinition, ...]:
    return RANK_DEFINITIONS


def get_rank_definition(rank_id: str) -> RankDefinition:
    return _RANK_BY_ID.get(rank_id) or _RANK_BY_ID[DEFAULT_RANK_ID]


def rank_definition_index(rank_id: str) -> int:
    for index, spec in enumerate(RANK_DEFINITIONS):
        if spec.id == rank_id:
            return index
    return 0
