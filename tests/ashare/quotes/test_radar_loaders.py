"""雷达卡片数据加载测试。"""

from vnpy_ashare.quotes.radar_catalog import RADAR_CARD_BY_ID
from vnpy_ashare.quotes.radar_loaders import load_screen_latest


def test_load_screen_latest_empty(monkeypatch) -> None:
    monkeypatch.setattr("vnpy_ashare.quotes.radar_loaders.get_latest_run", lambda: None)
    spec = RADAR_CARD_BY_ID["screen_latest"]
    data = load_screen_latest(spec)
    assert data.rows == ()
    assert "暂无选股记录" in data.empty_message
