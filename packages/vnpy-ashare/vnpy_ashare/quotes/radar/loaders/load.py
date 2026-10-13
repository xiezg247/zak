"""雷达卡片加载入口与整板并行加载。"""

from __future__ import annotations

from vnpy_ashare.data.download_concurrency import radar_board_max_workers, run_parallel_map
from vnpy_ashare.domain.time.market_hours import is_ashare_trading_session
from vnpy_ashare.quotes.radar.loaders.cancel import RadarLoadCancelled, raise_if_radar_load_cancelled
from vnpy_ashare.quotes.radar.loaders.discovery import load_discovery_moneyflow_intraday, load_discovery_volume_surge
from vnpy_ashare.quotes.radar.radar_card_snapshot_cache import (
    peek_radar_card_snapshot,
    put_radar_card_snapshot,
    radar_card_variant_key,
)
from vnpy_ashare.quotes.radar.radar_catalog import (
    DEFAULT_LEADER_PICK_VARIANT,
    DEFAULT_LIMIT_LADDER_VARIANT,
    DEFAULT_SCENARIO_VARIANT,
    DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    DEFAULT_SECTOR_VARIANT,
    RADAR_CARD_BY_ID,
)
from vnpy_ashare.quotes.radar.radar_first_board import load_first_board
from vnpy_ashare.quotes.radar.radar_horizon import load_outlook_horizon
from vnpy_ashare.quotes.radar.radar_horizon_predict import load_outlook_predict
from vnpy_ashare.quotes.radar.radar_leader_pick import LeaderPickVariant, load_leader_pick
from vnpy_ashare.quotes.radar.radar_limit_break import load_discovery_limit_break
from vnpy_ashare.quotes.radar.radar_limit_ladder import LimitLadderVariant, load_limit_ladder
from vnpy_ashare.quotes.radar.radar_market_emotion import load_market_emotion
from vnpy_ashare.quotes.radar.radar_models import RadarCardData
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
from vnpy_ashare.screener.data.screening_prefilter import (
    apply_recipe_prefilter_to_context,
    apply_sentiment_prefilter_to_context,
)
from vnpy_common.perf_trace import tracer

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
        "watchlist_short_term",
        "watchlist_intraday",
        "position_risk",
        "outlook_watch",
        "outlook_hold",
        "outlook_scenario",
        "outlook_predict",
    }
)


def incremental_refresh_radar_card_quotes(data: RadarCardData) -> RadarCardData:
    """仅刷新卡片行的现价与涨幅，不重算发现 / 板块等指标。"""
    if not data.rows:
        return data
    from vnpy_ashare.quotes.radar.radar_enrich import refresh_radar_rows_live_quotes

    refreshed = refresh_radar_rows_live_quotes(data.rows)
    return data.model_copy(update={"rows": refreshed})


def load_radar_card_uncached(
    card_id: str,
    *,
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
    sector_variant: str = DEFAULT_SECTOR_VARIANT,
    sector_flow_hot_variant: str = DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    leader_pick_variant: str = DEFAULT_LEADER_PICK_VARIANT,
    limit_ladder_variant: str = DEFAULT_LIMIT_LADDER_VARIANT,
    scenario_variant: str = DEFAULT_SCENARIO_VARIANT,
) -> dict[str, str]:
    return {
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
) -> tuple[str, RadarCardData | None, str | None, bool]:
    """返回 (card_id, data, error, needs_live_quote_refresh)。

    缓存命中时不在此单卡刷新行情，由 batch 汇总后一次拉取。
    """
    card_id, kwargs = item
    force_recompute = bool(kwargs.get("force_recompute", False))
    variant_key = radar_card_variant_key(card_id, variants)
    if not force_recompute and card_id in RADAR_SNAPSHOT_CARD_IDS:
        cached = peek_radar_card_snapshot(card_id, variant_key=variant_key)
        if cached is not None:
            needs_refresh = bool(is_ashare_trading_session() and cached.rows)
            return card_id, cached, None, needs_refresh
    try:
        data = load_radar_card_uncached(
            card_id,
            force_recompute=force_recompute,
            **variants,
        )
    except Exception as ex:
        return card_id, None, str(ex), False
    if card_id in RADAR_SNAPSHOT_CARD_IDS:
        put_radar_card_snapshot(card_id, data, variant_key=variant_key)
    return card_id, data, None, False


def _batch_max_workers(count: int) -> int:
    return radar_board_max_workers(item_count=count)


def _apply_batch_live_quote_refresh(
    pending: list[tuple[str, RadarCardData]],
) -> dict[str, RadarCardData]:
    """对 cache-hit 卡汇总 vt_symbol，一次 quotes_for_vt_symbols 后回填。"""
    if not pending:
        return {}
    from vnpy_ashare.quotes.radar.radar_enrich import (
        collect_radar_quote_vt_symbols,
        refresh_radar_card_quotes_from_map,
    )
    from vnpy_ashare.quotes.radar.radar_quotes import quotes_for_vt_symbols

    cards = [data for _, data in pending]
    vt_symbols = collect_radar_quote_vt_symbols(cards)
    quotes = quotes_for_vt_symbols(vt_symbols) if vt_symbols else {}
    return {
        card_id: refresh_radar_card_quotes_from_map(data, quotes)
        for card_id, data in pending
    }


def _load_radar_cards_in_context(
    items: list[tuple[str, dict[str, object]]],
    *,
    context_mode: str,
    variants: dict[str, str],
) -> tuple[dict[str, RadarCardData], dict[str, str]]:
    """在单一 ScreeningContext 内并行加载多张卡。"""
    raise_if_radar_load_cancelled()
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
        pending_refresh: list[tuple[str, RadarCardData]] = []
        for card_id, data, error, needs_refresh in pairs:
            if error is not None:
                errors[card_id] = error
            elif data is not None:
                if needs_refresh:
                    pending_refresh.append((card_id, data))
                else:
                    loaded[card_id] = data
        if pending_refresh:
            loaded.update(_apply_batch_live_quote_refresh(pending_refresh))

    if context_mode == "full":
        with screening_context_scope() as ctx:
            # preload_screening_context 已含 recipe prefilter，避免重复 apply
            preload_screening_context(ctx)
            apply_sentiment_prefilter_to_context(ctx)
            _run_batch()
    elif context_mode == "quote":
        with screening_context_scope() as ctx:
            preload_screening_context_quotes(ctx)
            apply_recipe_prefilter_to_context(ctx)
            _run_batch()
    else:
        _run_batch()

    raise_if_radar_load_cancelled()
    return loaded, errors


def load_radar_cards_batch(
    items: list[tuple[str, dict[str, object]]],
    *,
    sector_variant: str = DEFAULT_SECTOR_VARIANT,
    sector_flow_hot_variant: str = DEFAULT_SECTOR_FLOW_HOT_VARIANT,
    leader_pick_variant: str = DEFAULT_LEADER_PICK_VARIANT,
    limit_ladder_variant: str = DEFAULT_LIMIT_LADDER_VARIANT,
    scenario_variant: str = DEFAULT_SCENARIO_VARIANT,
) -> tuple[dict[str, RadarCardData], dict[str, str]]:
    """批量加载雷达卡片：按上下文类型分组，组内共享快照并并行计算。"""
    card_ids = ",".join(card_id for card_id, _ in items)
    try:
        with tracer.trace(f"radar.load_cards[{card_ids}]"):
            raise_if_radar_load_cancelled()
            variants = _radar_load_variants(
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
            bucket_modes = [(mode, buckets[mode]) for mode in ("full", "quote", "none") if buckets[mode]]
            for mode, batch_items in bucket_modes:
                raise_if_radar_load_cancelled()
                batch_loaded, batch_errors = _load_radar_cards_in_context(
                    batch_items,
                    context_mode=mode,
                    variants=variants,
                )
                loaded.update(batch_loaded)
                errors.update(batch_errors)
            return loaded, errors
    except RadarLoadCancelled:
        return {}, {}


def load_radar_card(
    card_id: str,
    *,
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
