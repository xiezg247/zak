"""雷达展望缓存键测试。"""

from vnpy_ashare.quotes.radar.radar_horizon_cache import horizon_cache_storage_key


def test_horizon_cache_storage_key_includes_strategy() -> None:
    assert horizon_cache_storage_key("watch_next", "AshareDoubleMaStrategy:10:20") == ("watch_next|AshareDoubleMaStrategy:10:20")


def test_horizon_cache_storage_key_without_strategy() -> None:
    assert horizon_cache_storage_key("watch_next", "") == "watch_next"
