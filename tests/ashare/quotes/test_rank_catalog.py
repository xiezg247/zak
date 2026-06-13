"""榜单注册表与 Redis 榜 key 辅助测试。"""

from vnpy_ashare.quotes.rank_catalog import (
    RANK_DEFINITIONS,
    get_rank_definition,
    list_rank_definitions,
    list_rank_groups,
    rank_definition_index,
    rank_definition_row,
)
from vnpy_ashare.quotes.redis_store import RANK_REDIS_FIELDS, rank_key


def test_rank_definitions_unique_ids() -> None:
    ids = [spec.id for spec in RANK_DEFINITIONS]
    assert len(ids) == len(set(ids))


def test_get_rank_definition_fallback() -> None:
    spec = get_rank_definition("unknown")
    assert spec.id == "change_pct"


def test_rank_definition_row_accounts_for_group_headers() -> None:
    assert rank_definition_row("change_pct") == 1
    assert rank_definition_index("change_pct") == 1
    assert rank_definition_row("unknown") == 0


def test_list_rank_definitions_contains_new_boards() -> None:
    titles = {spec.title for spec in list_rank_definitions()}
    assert "涨幅榜" in titles
    assert "跌幅榜" in titles
    assert "涨停" in titles
    assert "连板榜" in titles
    assert "临停" in titles
    assert "低开高走" in titles
    assert "量比榜" in titles
    assert "主力净流入" in titles
    assert "涨速" in titles
    assert "自选涨幅" in titles
    assert "换手榜" in titles


def test_list_rank_groups() -> None:
    assert list_rank_groups() == ("价格", "量能", "资金", "我的")


def test_rank_redis_fields_have_keys() -> None:
    for field in RANK_REDIS_FIELDS:
        assert rank_key(field).startswith("zak:rank:")
    assert "intraday_change_pct" in RANK_REDIS_FIELDS
    assert "volume_ratio" in RANK_REDIS_FIELDS
    assert "net_mf_amount" in RANK_REDIS_FIELDS
    assert "change_speed_5m" in RANK_REDIS_FIELDS
    assert "limit_times" in RANK_REDIS_FIELDS
