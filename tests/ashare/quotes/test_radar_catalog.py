"""雷达卡片注册表测试。"""

from vnpy_ashare.quotes.radar_catalog import (
    CARD_VARIANTS,
    RADAR_CARD_SPECS,
    RADAR_GRID_COLUMNS,
    SCREEN_TASK_VARIANTS,
    list_radar_cards,
    variants_for_card,
)


def test_radar_cards_count_and_categories() -> None:
    cards = list_radar_cards()
    assert len(cards) == 8
    categories = {card.category for card in cards}
    assert categories == {"screen", "discovery", "watchlist", "sector", "outlook"}
    assert RADAR_GRID_COLUMNS == 3


def test_radar_card_ids_unique() -> None:
    ids = [spec.id for spec in RADAR_CARD_SPECS]
    assert len(ids) == len(set(ids))


def test_screen_task_variants_defined() -> None:
    keys = {variant.key for variant in SCREEN_TASK_VARIANTS}
    assert keys == {"scheduled_intraday", "scheduled_post_close", "strategy"}


def test_card_variants_registry() -> None:
    assert variants_for_card("sector_theme") == CARD_VARIANTS["sector_theme"]
    assert variants_for_card("outlook_watch") == ()
    assert variants_for_card("outlook_hold") == ()
    assert variants_for_card("watchlist_intraday") == ()
