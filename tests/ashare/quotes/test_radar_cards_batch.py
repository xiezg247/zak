"""雷达批量加载：共享 ScreeningContext。"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401


def test_load_radar_cards_batch_groups_context_modes() -> None:
    from vnpy_ashare.quotes.radar.loaders.load import load_radar_cards_batch

    items = [
        ("leader_pick", {}),
        ("outlook_watch", {}),
        ("market_emotion", {}),
    ]
    full_calls: list[int] = []
    quote_calls: list[int] = []
    none_calls: list[int] = []

    def _fake_load(batch, *, context_mode, variants):
        if context_mode == "full":
            full_calls.append(len(batch))
        elif context_mode == "quote":
            quote_calls.append(len(batch))
        else:
            none_calls.append(len(batch))
        return {card_id: MagicMock() for card_id, _ in batch}, {}

    with patch(
        "vnpy_ashare.quotes.radar.loaders.load._load_radar_cards_in_context",
        side_effect=_fake_load,
    ):
        loaded, errors = load_radar_cards_batch(items)

    assert errors == {}
    assert set(loaded) == {"leader_pick", "outlook_watch", "market_emotion"}
    assert full_calls == [1]
    assert quote_calls == [1]
    assert none_calls == [1]
