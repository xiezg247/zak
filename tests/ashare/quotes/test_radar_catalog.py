"""雷达卡片注册表测试。"""

from vnpy_ashare.quotes.radar_catalog import (
    RADAR_CARD_SPECS,
    SCREEN_TASK_VARIANTS,
    list_radar_cards,
)


def test_radar_cards_count_and_categories() -> None:
    cards = list_radar_cards()
    assert len(cards) == 4
    categories = {card.category for card in cards}
    assert categories == {"screen", "discovery"}
    screen_cards = [card for card in cards if card.category == "screen"]
    discovery_cards = [card for card in cards if card.category == "discovery"]
    assert len(screen_cards) == 2
    assert len(discovery_cards) == 2


def test_radar_card_ids_unique() -> None:
    ids = [spec.id for spec in RADAR_CARD_SPECS]
    assert len(ids) == len(set(ids))


def test_screen_task_variants_defined() -> None:
    keys = {variant.key for variant in SCREEN_TASK_VARIANTS}
    assert keys == {"scheduled_intraday", "scheduled_post_close", "strategy"}
