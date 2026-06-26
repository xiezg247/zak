"""雷达卡片加载入口与整板并行加载。"""

from __future__ import annotations

import os

from vnpy_ashare.data.download_concurrency import run_parallel_map
from vnpy_ashare.quotes.radar.loaders.discovery import load_discovery_moneyflow_intraday, load_discovery_volume_surge
from vnpy_ashare.quotes.radar.radar_catalog import (
    DEFAULT_LEADER_PICK_VARIANT,
    DEFAULT_LIMIT_LADDER_VARIANT,
    DEFAULT_SCENARIO_VARIANT,
    DEFAULT_SCREEN_TASK_VARIANT,
    DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    DEFAULT_SECTOR_VARIANT,
    RADAR_CARD_BY_ID,
    RADAR_CARD_SPECS,
    RadarCardSpec,
)
from vnpy_ashare.quotes.radar.radar_first_board import load_first_board
from vnpy_ashare.quotes.radar.radar_horizon import load_outlook_horizon
from vnpy_ashare.quotes.radar.radar_horizon_predict import load_outlook_predict
from vnpy_ashare.quotes.radar.radar_leader_pick import LeaderPickVariant, load_leader_pick
from vnpy_ashare.quotes.radar.radar_limit_break import load_discovery_limit_break
from vnpy_ashare.quotes.radar.radar_limit_ladder import LimitLadderVariant, load_limit_ladder
from vnpy_ashare.quotes.radar.radar_market_emotion import load_market_emotion
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, enrich_radar_rows
from vnpy_ashare.quotes.radar.radar_position_risk import load_position_risk
from vnpy_ashare.quotes.radar.radar_sector import load_sector_theme
from vnpy_ashare.quotes.radar.radar_sector_flow_hot import SectorFlowHotVariant, load_sector_flow_hot
from vnpy_ashare.quotes.radar.radar_watchlist import load_watchlist_intraday
from vnpy_ashare.quotes.radar.radar_watchlist_short_term import load_watchlist_short_term
from vnpy_ashare.screener.data.screening_context import (
    preload_screening_context,
    preload_screening_context_quotes,
    screening_context_scope,
)
from vnpy_ashare.quotes.radar.radar_card_snapshot_cache import (
    peek_radar_card_snapshot,
    put_radar_card_snapshot,
    radar_card_variant_key,
)
from vnpy_ashare.screener.data.screening_sentiment_prefilter import (
    apply_recipe_prefilter_to_context,
    apply_sentiment_prefilter_to_context,
)

RADAR_FULL_CONTEXT_CARD_IDS = frozenset(
    {
        "discovery_volume_surge",
        "discovery_moneyflow_intraday",
        "discovery_limit_ladder",
        "discovery_limit_break",
        "watchlist_intraday",
        "watchlist_short_term",
        "position_risk",
        "sector_theme",
        "sector_flow_hot",
        "leader_pick",
    }
)

RADAR_QUOTE_CONTEXT_CARD_IDS = frozenset(
    {
        "outlook_watch",
        "outlook_hold",
        "outlook_scenario",
        "outlook_predict",
    }
)

RADAR_SNAPSHOT_CARD_IDS = frozenset(
    {
        "market_emotion",
        "leader_pick",
        "discovery_volume_surge",
        "discovery_moneyflow_intraday",
        "discovery_limit_ladder",
        "discovery_limit_break",
        "sector_theme",
        "sector_flow_hot",
    }
)


def incremental_refresh_radar_card_quotes(data: RadarCardData) -> RadarCardData:
    """仅刷新卡片行的现价与涨幅，不重算发现 / 板块等指标。"""
    if not data.rows:
        return data
    with screening_context_scope() as ctx:
        preload_screening_context_quotes(ctx)
        enriched = enrich_radar_rows(data.rows)
    return data.model_copy(update={"rows": enriched})


def load_radar_card_uncached(
    card_id: str,
    *,
    screen_task_variant: str = DEFAULT_SCREEN_TASK_VARIANT,
    sector_variant: str = DEFAULT_SECTOR_VARIANT,
    sector_flow_hot_variant: str = DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    leader_pick_variant: str = DEFAULT_LEADER_PICK_VARIANT,
    limit_ladder_variant: str = DEFAULT_LIMIT_LADDER_VARIANT,
    scenario_variant: str = DEFAULT_SCENARIO_VARIANT,
    force_recompute: bool = False,
) -> RadarCardData:
    """加载单张雷达卡片（无额外上下文包装）。"""
    spec = RADAR_CARD_BY_ID.get(card_id)
    if spec is None:
        msg = f"未知雷达卡片：{card_id}"
        raise ValueError(msg)
    if spec.id == "market_emotion":
        return load_market_emotion(spec)
    if spec.id == "discovery_volume_surge":
        return load_discovery_volume_surge(spec)
    if spec.id == "discovery_moneyflow_intraday":
        return load_discovery_moneyflow_intraday(spec)
    if spec.id == "discovery_limit_ladder":
        if limit_ladder_variant == "first_board":
            return load_first_board(spec)
        ladder_variant: LimitLadderVariant = "by_sector" if limit_ladder_variant == "by_sector" else "by_height"
        return load_limit_ladder(spec, variant=ladder_variant)
    if spec.id == "discovery_limit_break":
        return load_discovery_limit_break(spec)
    if spec.id == "watchlist_intraday":
        return load_watchlist_intraday(spec)
    if spec.id == "watchlist_short_term":
        return load_watchlist_short_term(spec)
    if spec.id == "position_risk":
        return load_position_risk(spec)
    if spec.id == "sector_flow_hot":
        hot_variant: SectorFlowHotVariant = "concept" if sector_flow_hot_variant == "concept" else "industry"
        return load_sector_flow_hot(spec, variant=hot_variant)
    if spec.id == "sector_theme":
        return load_sector_theme(spec, variant=sector_variant)
    if spec.id == "leader_pick":
        pick_variant: LeaderPickVariant = "mainline" if leader_pick_variant != "all_market" else "all_market"
        return load_leader_pick(spec, variant=pick_variant)
    if spec.id in ("outlook_watch", "outlook_hold"):
        return load_outlook_horizon(spec, force_recompute=force_recompute)
    if spec.id == "outlook_scenario":
        return load_outlook_horizon(
            spec,
            variant=scenario_variant,
            force_recompute=force_recompute,
        )
    if spec.id == "outlook_predict":
        return load_outlook_predict(spec, force_recompute=force_recompute)
    msg = f"未实现的雷达卡片加载器：{card_id}"
    raise ValueError(msg)


def _radar_load_variants(
    *,
    screen_task_variant: str = DEFAULT_SCREEN_TASK_VARIANT,
    sector_variant: str = DEFAULT_SECTOR_VARIANT,
    sector_flow_hot_variant: str = DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    leader_pick_variant: str = DEFAULT_LEADER_PICK_VARIANT,
    limit_ladder_variant: str = DEFAULT_LIMIT_LADDER_VARIANT,
    scenario_variant: str = DEFAULT_SCENARIO_VARIANT,
) -> dict[str, str]:
    return {
        "screen_task_variant": screen_task_variant,
        "sector_variant": sector_variant,
        "sector_flow_hot_variant": sector_flow_hot_variant,
        "leader_pick_variant": leader_pick_variant,
        "limit_ladder_variant": limit_ladder_variant,
        "scenario_variant": scenario_variant,
    }


def _load_radar_card_item(
    item: tuple[str, dict[str, object]],
    *,
    variants: dict[str, str],
) -> tuple[str, RadarCardData | None, str | None]:
    card_id, kwargs = item
    force_recompute = bool(kwargs.get("force_recompute", False))
    variant_key = radar_card_variant_key(card_id, variants)
    if not force_recompute and card_id in RADAR_SNAPSHOT_CARD_IDS:
        cached = peek_radar_card_snapshot(card_id, variant_key=variant_key)
        if cached is not None:
            return card_id, cached, None
    try:
        data = load_radar_card_uncached(
            card_id,
            force_recompute=force_recompute,
            **variants,
        )
    except Exception as ex:
        return card_id, None, str(ex)
    if card_id in RADAR_SNAPSHOT_CARD_IDS:
        put_radar_card_snapshot(card_id, data, variant_key=variant_key)
    return card_id, data, None


def _batch_max_workers(count: int) -> int:
    raw = os.getenv("RADAR_BOARD_MAX_WORKERS", "4").strip()
    try:
        max_workers = max(1, min(int(raw), 8))
    except ValueError:
        max_workers = 4
    return min(max_workers, max(1, count))


def _load_radar_cards_in_context(
    items: list[tuple[str, dict[str, object]]],
    *,
    context_mode: str,
    variants: dict[str, str],
) -> tuple[dict[str, RadarCardData], dict[str, str]]:
    """在单一 ScreeningContext 内并行加载多张卡。"""
    if not items:
        return {}, {}

    loaded: dict[str, RadarCardData] = {}
    errors: dict[str, str] = {}

    def _run_batch() -> None:
        pairs = run_parallel_map(
            items,
            lambda item: _load_radar_card_item(item, variants=variants),
            max_workers=_batch_max_workers(len(items)),
        )
        for card_id, data, error in pairs:
            if error is not None:
                errors[card_id] = error
            elif data is not None:
                loaded[card_id] = data

    if context_mode == "full":
        with screening_context_scope() as ctx:
            preload_screening_context(ctx)
            apply_recipe_prefilter_to_context(ctx)
            apply_sentiment_prefilter_to_context(ctx)
            _run_batch()
    elif context_mode == "quote":
        with screening_context_scope() as ctx:
            preload_screening_context_quotes(ctx)
            apply_recipe_prefilter_to_context(ctx)
            _run_batch()
    else:
        _run_batch()

    return loaded, errors


def load_radar_cards_batch(
    items: list[tuple[str, dict[str, object]]],
    *,
    screen_task_variant: str = DEFAULT_SCREEN_TASK_VARIANT,
    sector_variant: str = DEFAULT_SECTOR_VARIANT,
    sector_flow_hot_variant: str = DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    leader_pick_variant: str = DEFAULT_LEADER_PICK_VARIANT,
    limit_ladder_variant: str = DEFAULT_LIMIT_LADDER_VARIANT,
    scenario_variant: str = DEFAULT_SCENARIO_VARIANT,
) -> tuple[dict[str, RadarCardData], dict[str, str]]:
    """批量加载雷达卡片：按上下文类型分组，组内共享快照并并行计算。"""
    variants = _radar_load_variants(
        screen_task_variant=screen_task_variant,
        sector_variant=sector_variant,
        sector_flow_hot_variant=sector_flow_hot_variant,
        leader_pick_variant=leader_pick_variant,
        limit_ladder_variant=limit_ladder_variant,
        scenario_variant=scenario_variant,
    )
    buckets: dict[str, list[tuple[str, dict[str, object]]]] = {"full": [], "quote": [], "none": []}
    for item in items:
        card_id, _kwargs = item
        if card_id in RADAR_FULL_CONTEXT_CARD_IDS:
            buckets["full"].append(item)
        elif card_id in RADAR_QUOTE_CONTEXT_CARD_IDS:
            buckets["quote"].append(item)
        else:
            buckets["none"].append(item)

    loaded: dict[str, RadarCardData] = {}
    errors: dict[str, str] = {}
    for mode in ("full", "quote", "none"):
        batch_loaded, batch_errors = _load_radar_cards_in_context(buckets[mode], context_mode=mode, variants=variants)
        loaded.update(batch_loaded)
        errors.update(batch_errors)
    return loaded, errors


def load_radar_card(
    card_id: str,
    *,
    screen_task_variant: str = DEFAULT_SCREEN_TASK_VARIANT,
    sector_variant: str = DEFAULT_SECTOR_VARIANT,
    sector_flow_hot_variant: str = DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    leader_pick_variant: str = DEFAULT_LEADER_PICK_VARIANT,
    limit_ladder_variant: str = DEFAULT_LIMIT_LADDER_VARIANT,
    scenario_variant: str = DEFAULT_SCENARIO_VARIANT,
    force_recompute: bool = False,
) -> RadarCardData:
    """加载单张雷达卡片；行情类卡片自动复用 ScreeningContext。"""
    loaded, errors = load_radar_cards_batch(
        [(card_id, {"force_recompute": force_recompute})],
        screen_task_variant=screen_task_variant,
        sector_variant=sector_variant,
        sector_flow_hot_variant=sector_flow_hot_variant,
        leader_pick_variant=leader_pick_variant,
        limit_ladder_variant=limit_ladder_variant,
        scenario_variant=scenario_variant,
    )
    if card_id in errors:
        raise ValueError(errors[card_id])
    data = loaded.get(card_id)
    if data is None:
        msg = f"雷达卡片加载失败：{card_id}"
        raise ValueError(msg)
    return data


def load_radar_board(
    *,
    screen_task_variant: str = DEFAULT_SCREEN_TASK_VARIANT,
    sector_variant: str = DEFAULT_SECTOR_VARIANT,
) -> dict[str, RadarCardData]:
    """加载全部雷达卡片（共享 ScreeningContext + 并行加载）。"""
    items = [(spec.id, {}) for spec in RADAR_CARD_SPECS]
    loaded, errors = load_radar_cards_batch(
        items,
        screen_task_variant=screen_task_variant,
        sector_variant=sector_variant,
    )
    if errors:
        first_id = next(iter(errors))
        raise ValueError(f"{first_id}: {errors[first_id]}")
    return loaded
