"""雷达变体 wiring 纯函数测试。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.radar_catalog import (
    DEFAULT_LEADER_PICK_VARIANT,
    DEFAULT_LIMIT_LADDER_VARIANT,
    DEFAULT_SCENARIO_VARIANT,
    DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    DEFAULT_SECTOR_VARIANT,
)
from vnpy_ashare.ui.quotes.radar.variant_wiring import (
    build_default_card_variants,
    card_load_variants,
    mirrors_sector_variant,
    persist_variant_preference,
)


def test_build_default_card_variants_keys(monkeypatch) -> None:
    monkeypatch.setattr(
        "vnpy_ashare.ui.quotes.radar.variant_wiring.load_predict_model_mode",
        lambda: "baseline",
    )
    variants = build_default_card_variants()
    assert variants["sector_theme"] == DEFAULT_SECTOR_VARIANT
    assert variants["leader_pick"] == DEFAULT_LEADER_PICK_VARIANT
    assert variants["discovery_limit_ladder"] == DEFAULT_LIMIT_LADDER_VARIANT
    assert variants["outlook_scenario"] == DEFAULT_SCENARIO_VARIANT
    assert variants["outlook_predict"] == "baseline"


def test_card_load_variants_maps_and_defaults() -> None:
    kwargs = card_load_variants(
        {
            "sector_theme": "breadth",
            "leader_pick": "all_market",
        }
    )
    assert kwargs == {
        "sector_variant": "breadth",
        "sector_flow_hot_variant": DEFAULT_SECTOR_FLOW_HOT_VARIANT,
        "leader_pick_variant": "all_market",
        "limit_ladder_variant": DEFAULT_LIMIT_LADDER_VARIANT,
        "scenario_variant": DEFAULT_SCENARIO_VARIANT,
    }


def test_mirrors_sector_variant() -> None:
    assert mirrors_sector_variant("sector_theme")
    assert not mirrors_sector_variant("leader_pick")


def test_persist_variant_preference(monkeypatch) -> None:
    saved: list[str] = []
    monkeypatch.setattr(
        "vnpy_ashare.quotes.radar.predict.predict_prefs.save_predict_model_mode",
        lambda mode: saved.append(mode),
    )
    persist_variant_preference("leader_pick", "x")
    assert saved == []
    persist_variant_preference("outlook_predict", "baseline")
    assert saved == ["baseline"]

