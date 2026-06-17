"""雷达预测扫描（粗筛池 + 统计基线排序）。"""

from __future__ import annotations

from pydantic import Field

from vnpy_ashare.domain.base import FrozenModel, MutableModel

from typing import Any

from vnpy_ashare.domain.symbols import parse_stock_symbol
from vnpy_ashare.domain.time.china import format_china_datetime_minute
from vnpy_ashare.quotes.core.quote_rows import quote_rows_by_vt_symbol
from vnpy_ashare.quotes.radar.predict.baseline_ranker import BaselinePredictHit, rank_baseline_predict
from vnpy_ashare.quotes.radar.predict.predict_cache import put_predict_cache
from vnpy_ashare.quotes.radar.predict.predict_prefs import PredictModelMode, load_predict_model_mode
from vnpy_ashare.quotes.radar.predict.types import PredictHit
from vnpy_ashare.quotes.radar.radar_horizon_scan import prefilter_horizon_universe
from vnpy_ashare.quotes.radar.radar_horizon_stats import HorizonScanStats
from vnpy_ashare.quotes.radar.radar_models import RadarRow
from vnpy_ashare.quotes.radar.radar_pool import collect_outlook_exclusion_vt_symbols, name_map_for_symbols
from vnpy_ashare.screener.data.data_source import load_screening_quote_snapshot
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError

PREDICT_VARIANT_BASELINE = "predict_baseline"


class PredictScanResult(FrozenModel):
    variant: str = Field(description="变体标识")
    rows: tuple[RadarRow, ...] = Field(description="数据行列表")
    stats: HorizonScanStats = Field(description="扫描统计")
    model_label: str = Field(description="模型标签")
    computed_at: str = Field(description="计算时间")


def _quote_rows_for_prefilter(prefilter: list[str]) -> list[dict[str, Any]]:
    if not prefilter:
        return []
    try:
        snapshot = load_screening_quote_snapshot()
    except MarketQuotesLoadError:
        return []
    wanted = set(prefilter)
    return [dict(row) for row in snapshot.rows if str(row.get("vt_symbol") or "").strip() in wanted]


def _baseline_to_hit(hit: BaselinePredictHit) -> PredictHit:
    return PredictHit(
        vt_symbol=hit.vt_symbol,
        score=hit.score,
        p_up=hit.p_up,
        score_label="基准分",
        model_label="统计基线",
    )


def rank_predict_hits(
    quote_rows: list[dict[str, Any]],
    *,
    top_n: int,
    mode: PredictModelMode | None = None,
) -> tuple[list[PredictHit], str, str]:
    """统计基线排序（auto / baseline 均走基线；后续可扩展 ML 模型）。"""
    _ = mode or load_predict_model_mode()
    limit = max(1, int(top_n))
    baseline_hits = [_baseline_to_hit(hit) for hit in rank_baseline_predict(quote_rows)[:limit]]
    return baseline_hits, PREDICT_VARIANT_BASELINE, "统计基线"


def _hit_to_row(hit: PredictHit, *, name_map: dict[str, str], quote_row: dict[str, Any]) -> RadarRow:
    item = parse_stock_symbol(hit.vt_symbol)
    symbol = item.symbol if item is not None else hit.vt_symbol.split(".")[0]
    name = name_map.get(hit.vt_symbol) or str(quote_row.get("name") or symbol)
    price = quote_row.get("last_price") or quote_row.get("close")
    change = quote_row.get("change_pct") if quote_row.get("change_pct") not in (None, "") else quote_row.get("pct_chg")
    return RadarRow(
        vt_symbol=hit.vt_symbol,
        name=name,
        symbol=symbol,
        price=float(price) if isinstance(price, (int, float)) else None,
        change_pct=float(change) if isinstance(change, (int, float)) else None,
        metric_label="看涨概率",
        metric_value=f"{hit.p_up * 100:.0f}%",
        sub_label=hit.score_label,
        sub_value=f"{hit.score:.1f}",
    )


def scan_predict(*, top_n: int = 8) -> PredictScanResult:
    """全市场粗筛后做预测排序。"""
    excluded = collect_outlook_exclusion_vt_symbols()
    prefilter, stats = prefilter_horizon_universe(excluded)
    quote_rows = _quote_rows_for_prefilter(prefilter)
    hits, variant, model_label = rank_predict_hits(quote_rows, top_n=top_n)
    name_map = name_map_for_symbols([hit.vt_symbol for hit in hits])
    row_by_vt = quote_rows_by_vt_symbol(quote_rows)
    rows = tuple(_hit_to_row(hit, name_map=name_map, quote_row=row_by_vt.get(hit.vt_symbol, {"vt_symbol": hit.vt_symbol})) for hit in hits)
    refined_stats = HorizonScanStats(
        scanned_total=stats.scanned_total,
        excluded_count=stats.excluded_count,
        prefilter_total=stats.prefilter_total,
        refined_total=len(hits),
        kline_missing=stats.kline_missing,
    )
    return PredictScanResult(
        variant=variant,
        rows=rows,
        stats=refined_stats,
        model_label=model_label,
        computed_at=format_china_datetime_minute(),
    )


def scan_predict_baseline(*, top_n: int = 8) -> PredictScanResult:
    """仅统计基线（测试 / 对照）。"""
    excluded = collect_outlook_exclusion_vt_symbols()
    prefilter, stats = prefilter_horizon_universe(excluded)
    quote_rows = _quote_rows_for_prefilter(prefilter)
    hits = [_baseline_to_hit(hit) for hit in rank_baseline_predict(quote_rows)[: max(1, int(top_n))]]
    name_map = name_map_for_symbols([hit.vt_symbol for hit in hits])
    row_by_vt = quote_rows_by_vt_symbol(quote_rows)
    rows = tuple(_hit_to_row(hit, name_map=name_map, quote_row=row_by_vt.get(hit.vt_symbol, {"vt_symbol": hit.vt_symbol})) for hit in hits)
    return PredictScanResult(
        variant=PREDICT_VARIANT_BASELINE,
        rows=rows,
        stats=HorizonScanStats(
            scanned_total=stats.scanned_total,
            excluded_count=stats.excluded_count,
            prefilter_total=stats.prefilter_total,
            refined_total=len(hits),
            kline_missing=stats.kline_missing,
        ),
        model_label="统计基线",
        computed_at=format_china_datetime_minute(),
    )


def predict_empty_message(stats: HorizonScanStats, *, card_title: str) -> str:
    if stats.prefilter_total == 0 and stats.scanned_total == 0:
        return "暂无全市场行情，请先同步标的或等待行情采集。"
    if stats.prefilter_total == 0:
        return "粗筛池为空，请确认本地日 K 与行情数据已就绪。"
    return f"当前无符合「{card_title}」条件的标的（已扫描 {stats.scanned_total} 只）"


def run_predict_scan(*, top_n: int = 8) -> PredictScanResult:
    """执行预测扫描并写入缓存。"""
    scan = scan_predict(top_n=top_n)

    put_predict_cache(
        variant=scan.variant,
        rows=scan.rows,
        stats=scan.stats,
        model_label=scan.model_label,
        computed_at=scan.computed_at,
    )
    return scan


def run_predict_baseline_scan(*, top_n: int = 8) -> PredictScanResult:
    """仅基线扫描并写缓存（兼容旧调用）。"""
    scan = scan_predict_baseline(top_n=top_n)

    put_predict_cache(
        variant=scan.variant,
        rows=scan.rows,
        stats=scan.stats,
        model_label=scan.model_label,
        computed_at=scan.computed_at,
    )
    return scan


def build_predict_subtitle(
    *,
    horizon_days: int,
    model_label: str,
    scanned_total: int,
    top_count: int,
    model_caption: str = "",
) -> str:
    base = f"约 {horizon_days} 日 · {model_label} · 已扫 {scanned_total} 只 · Top {top_count} · 模型估计非保证收益"
    if model_caption:
        return f"{base} · {model_caption}"
    return base
