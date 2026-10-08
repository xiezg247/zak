"""雷达卡片变体 → loader kwargs 映射（纯函数，供 controller / 测试复用）。"""

from __future__ import annotations

from collections.abc import Mapping

from vnpy_ashare.quotes.radar.predict.predict_prefs import load_predict_model_mode
from vnpy_ashare.quotes.radar.radar_catalog import (
    DEFAULT_LEADER_PICK_VARIANT,
    DEFAULT_LIMIT_LADDER_VARIANT,
    DEFAULT_SCENARIO_VARIANT,
    DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    DEFAULT_SECTOR_VARIANT,
)

# card_id → load_radar_cards_batch / Radar*LoadWorker 参数名
_CARD_ID_TO_LOAD_KW: tuple[tuple[str, str, str], ...] = (
    ("sector_theme", "sector_variant", DEFAULT_SECTOR_VARIANT),
    ("sector_flow_hot", "sector_flow_hot_variant", DEFAULT_SECTOR_FLOW_HOT_VARIANT),
    ("leader_pick", "leader_pick_variant", DEFAULT_LEADER_PICK_VARIANT),
    ("discovery_limit_ladder", "limit_ladder_variant", DEFAULT_LIMIT_LADDER_VARIANT),
    ("outlook_scenario", "scenario_variant", DEFAULT_SCENARIO_VARIANT),
)


def build_default_card_variants() -> dict[str, str]:
    """控制器初始变体表（含预测模型偏好）。"""
    return {
        "sector_theme": DEFAULT_SECTOR_VARIANT,
        "leader_pick": DEFAULT_LEADER_PICK_VARIANT,
        "discovery_limit_ladder": DEFAULT_LIMIT_LADDER_VARIANT,
        "outlook_scenario": DEFAULT_SCENARIO_VARIANT,
        "outlook_predict": load_predict_model_mode(),
    }


def card_load_variants(card_variants: Mapping[str, str]) -> dict[str, str]:
    """将 UI 侧 card_id→variant 映射为 loader kwargs。"""
    return {
        load_kw: str(card_variants.get(card_id) or default)
        for card_id, load_kw, default in _CARD_ID_TO_LOAD_KW
    }
