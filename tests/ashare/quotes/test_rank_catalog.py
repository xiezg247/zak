"""榜单注册表与 Redis 榜 key 辅助测试。"""

from vnpy_ashare.quotes.rank_catalog import (
    RANK_DEFINITIONS,
    get_rank_definition,
    list_rank_definitions,
    rank_definition_index,
)
from vnpy_ashare.quotes.redis_store import RANK_REDIS_FIELDS, rank_key


def test_rank_definitions_unique_ids() -> None:
    ids = [spec.id for spec in RANK_DEFINITIONS]
    assert len(ids) == len(set(ids))


def test_get_rank_definition_fallback() -> None:
    spec = get_rank_definition("unknown")
    assert spec.id == "change_pct"


def test_rank_definition_index() -> None:
    assert rank_definition_index("change_pct") == 0
    assert rank_definition_index("unknown") == 0


def test_list_rank_definitions_contains_core_boards() -> None:
    titles = {spec.title for spec in list_rank_definitions()}
    assert "涨幅榜" in titles
    assert "跌幅榜" in titles
    assert "换手榜" in titles


def test_rank_redis_fields_have_keys() -> None:
    for field in RANK_REDIS_FIELDS:
        assert rank_key(field).startswith("zak:rank:")
