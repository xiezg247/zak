"""雷达共振卡片权重（可覆盖内置默认）。"""

from __future__ import annotations

from vnpy_ashare.config.preferences._settings import get_settings
from vnpy_ashare.config.preferences._user_pref import load_json_pref, save_json_pref

_KEY_PREFIX = "quotes/radar/resonance_weight/"
_PREF_NAMESPACE = "radar"
_PREF_KEY = "resonance_weights"

DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS: dict[str, float] = {
    "discovery_volume_surge": 2.0,
    "discovery_moneyflow_intraday": 2.0,
    "discovery_limit_ladder": 2.0,
    "watchlist_intraday": 1.5,
    "watchlist_short_term": 1.8,
    "position_risk": 1.0,
    "sector_theme": 1.5,
    "sector_flow_hot": 1.5,
    "leader_pick": 2.5,
    "outlook_watch": 0.75,
    "outlook_hold": 0.75,
    "outlook_scenario": 0.75,
    "outlook_predict": 1.0,
}

RADAR_CARDS_EXCLUDED_FROM_RESONANCE: frozenset[str] = frozenset(
    {
        "market_emotion",
        "discovery_limit_break",
    }
)

_WEIGHT_LABELS: dict[str, str] = {
    "market_emotion": "盘面·环境",
    "discovery_volume_surge": "发现·放量异动",
    "discovery_moneyflow_intraday": "发现·资金异动",
    "discovery_limit_ladder": "发现·连板梯队",
    "discovery_limit_break": "发现·炸板断板",
    "watchlist_intraday": "自选·异动",
    "watchlist_short_term": "自选·短线关注",
    "position_risk": "持仓·风控",
    "sector_theme": "板块·主线",
    "sector_flow_hot": "板块·资金热度",
    "leader_pick": "选股·龙头",
    "outlook_watch": "未来·关注",
    "outlook_hold": "未来·可持",
    "outlook_scenario": "未来·情景",
    "outlook_predict": "未来·预测",
}

_MIGRATE_KEYS = tuple(f"{_KEY_PREFIX}{card_id}" for card_id in DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS)


def list_radar_resonance_weight_items() -> tuple[tuple[str, str, float], ...]:
    """(card_id, 展示名, 默认权重)。"""
    return tuple(
        (card_id, _WEIGHT_LABELS.get(card_id, card_id), DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS[card_id]) for card_id in DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS
    )


def _load_resonance_from_qsettings() -> dict[str, float]:
    settings = get_settings()
    weights = dict(DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS)
    for card_id in DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS:
        raw = settings.value(f"{_KEY_PREFIX}{card_id}")
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            weights[card_id] = round(value, 2)
    return weights


def _merge_resonance_weights(stored: object) -> dict[str, float]:
    weights = dict(DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS)
    if isinstance(stored, dict):
        for card_id, raw in stored.items():
            if card_id not in weights:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value > 0:
                weights[card_id] = round(value, 2)
    return weights


def load_radar_resonance_weights() -> dict[str, float]:
    stored = load_json_pref(
        _PREF_NAMESPACE,
        _PREF_KEY,
        load_legacy=_load_resonance_from_qsettings,
        migrate_keys=_MIGRATE_KEYS,
    )
    return _merge_resonance_weights(stored)


def save_radar_resonance_weights(weights: dict[str, float]) -> None:
    payload: dict[str, float] = {}
    for card_id, default in DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS.items():
        value = float(weights.get(card_id, default))
        payload[card_id] = round(max(0.1, min(value, 5.0)), 2)
    save_json_pref(_PREF_NAMESPACE, _PREF_KEY, payload)


SHORT_TERM_RADAR_RESONANCE_WEIGHTS: dict[str, float] = {
    "discovery_volume_surge": 2.5,
    "discovery_moneyflow_intraday": 2.5,
    "discovery_limit_ladder": 2.5,
    "watchlist_intraday": 1.25,
    "watchlist_short_term": 2.0,
    "sector_theme": 1.5,
    "sector_flow_hot": 1.75,
    "leader_pick": 3.0,
    "outlook_watch": 0.5,
    "outlook_hold": 0.5,
    "outlook_scenario": 0.5,
    "outlook_predict": 0.5,
}


def apply_short_term_radar_resonance_weights() -> dict[str, float]:
    """D-03：一键应用「短线龙头」共振权重预设。"""
    save_radar_resonance_weights(SHORT_TERM_RADAR_RESONANCE_WEIGHTS)
    return load_radar_resonance_weights()


def reset_radar_resonance_weights_to_default() -> dict[str, float]:
    save_radar_resonance_weights(DEFAULT_RADAR_CARD_RESONANCE_WEIGHTS)
    return load_radar_resonance_weights()


def radar_card_resonance_weight(card_id: str) -> float:
    if card_id in RADAR_CARDS_EXCLUDED_FROM_RESONANCE:
        return 0.0
    return float(load_radar_resonance_weights().get(card_id, 1.0))


def radar_card_participates_in_resonance(card_id: str) -> bool:
    return card_id not in RADAR_CARDS_EXCLUDED_FROM_RESONANCE
