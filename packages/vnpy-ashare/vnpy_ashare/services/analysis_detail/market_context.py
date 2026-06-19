"""投研团队：轻量市场环境预取（供 Chief 引用，不新增子 Agent）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from vnpy_ashare.ai.context.store import get_market_overview_context
from vnpy_ashare.domain.trading.signal_benchmark import (
    compute_relative_index_excess,
    resolve_benchmark_return_pct,
)
from vnpy_ashare.integrations.tushare.factors import fetch_stock_industry_l1_map, fetch_stock_industry_map
from vnpy_ashare.quotes.core.quote_rows import get_market_quotes_cache
from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot
from vnpy_ashare.quotes.market.market_overview_loaders import SectorRankItem, load_sector_ranks
from vnpy_ashare.services.analysis_detail.risk_metrics import fetch_market_sentiment
from vnpy_common.domain.serialize import dump_python

if TYPE_CHECKING:
    from vnpy_ashare.domain.symbols.stock import StockItem
    from vnpy_ashare.services.analysis import AnalysisService

LOOKBACK_DAYS = 60
BENCHMARK_LABEL = "沪深300"


def _industry_from_diagnose(diagnose: dict[str, Any] | None) -> str | None:
    if not diagnose or diagnose.get("error"):
        return None
    quote = diagnose.get("quote") or {}
    industry = str(quote.get("industry") or "").strip()
    return industry or None


def _lookup_industry(ts_code: str) -> str | None:
    try:
        value = (fetch_stock_industry_map().get(ts_code) or "").strip()
        return value or None
    except Exception:
        return None


def _resolve_industry(item: StockItem, diagnose: dict[str, Any] | None) -> str | None:
    return _industry_from_diagnose(diagnose) or _lookup_industry(item.ts_code)


def _lookup_industry_l1(ts_code: str) -> str | None:
    try:
        value = (fetch_stock_industry_l1_map().get(ts_code) or "").strip()
        return value or None
    except Exception:
        return None


def _load_sector_ranks() -> list[SectorRankItem]:
    cached = get_market_quotes_cache()
    if cached:
        return load_sector_ranks(cached)
    return []


def _sector_snapshot(
    industry: str | None,
    sectors: list[SectorRankItem],
    *,
    industry_l1: str | None = None,
) -> dict[str, Any] | None:
    if not industry:
        return None
    base: dict[str, Any] = {"industry": industry}
    if industry_l1:
        base["industry_l1"] = industry_l1
    if not sectors:
        return {**base, "note": "暂无行业榜数据（需市场页行情缓存）"}
    for rank, item in enumerate(sectors, start=1):
        if item.industry != industry:
            continue
        return {
            **base,
            "rank": rank,
            "total_sectors": len(sectors),
            "avg_change_pct": item.avg_change_pct,
            "stock_count": item.count,
        }
    return {**base, "note": "当日行业榜中未找到该行业（样本不足或未收录）"}


def _build_summary_lines(payload: dict[str, Any]) -> list[str]:
    lines: list[str] = []

    benchmark = payload.get("benchmark") or {}
    bench_ret = benchmark.get(f"return_pct_{LOOKBACK_DAYS}d")
    if bench_ret is not None:
        lines.append(f"{BENCHMARK_LABEL} 近{LOOKBACK_DAYS}日 {bench_ret:+.2f}%")

    stock_vs = payload.get("stock_vs_benchmark") or {}
    excess = stock_vs.get("excess_pct")
    if excess is not None:
        lines.append(f"标的相对{BENCHMARK_LABEL}超额 {excess:+.2f}%")

    sentiment = payload.get("market_sentiment") or {}
    if sentiment.get("fear_greed_index") is not None:
        label = sentiment.get("fear_greed_label") or ""
        lines.append(f"恐贪指数 {sentiment['fear_greed_index']:.0f}{(' ' + label) if label else ''}")

    sector = payload.get("sector") or {}
    if sector.get("rank") is not None and sector.get("avg_change_pct") is not None:
        lines.append(
            f"所属行业「{sector['industry']}」当日涨幅排名第 {sector['rank']}/{sector.get('total_sectors', '?')} （均涨 {sector['avg_change_pct']:+.2f}%）"
        )
    elif sector.get("industry"):
        lines.append(f"所属行业：{sector['industry']}")

    overview = payload.get("overview") or {}
    breadth = str(overview.get("breadth_line") or "").strip()
    if breadth and "暂无" not in breadth:
        lines.append(breadth)

    return lines


def build_team_market_context(
    service: AnalysisService,
    item: StockItem,
    *,
    diagnose: dict[str, Any] | None = None,
    lookback_days: int = LOOKBACK_DAYS,
) -> dict[str, Any]:
    """构建 Chief 可用的市场环境包（本地 K 线 + 可选大盘概览缓存）。"""
    bar_service = service.engine.bar_service
    benchmark_pct = resolve_benchmark_return_pct(bar_service, lookback=lookback_days)
    stock_return = bar_service.get_return(
        item.symbol,
        item.exchange,
        "daily",
        lookback_days=lookback_days,
    )
    stock_pct = stock_return.get("return_pct")
    excess_pct = compute_relative_index_excess(
        bar_service,
        item.symbol,
        item.exchange,
        lookback=lookback_days,
        benchmark_pct=benchmark_pct,
    )

    overview_ctx = get_market_overview_context()
    overview: dict[str, Any] | None = None
    if overview_ctx:
        overview = {
            "source": "market_page_cache",
            "index_lines": overview_ctx.get("index_lines") or [],
            "breadth_line": overview_ctx.get("breadth_line"),
            "environment_line": overview_ctx.get("environment_line"),
            "sector_lines": overview_ctx.get("sector_lines") or [],
        }

    sentiment = fetch_market_sentiment()
    if sentiment is None and overview_ctx:
        env_line = str(overview_ctx.get("environment_line") or "")
        if "恐贪" in env_line:
            overview = overview or {"source": "market_page_cache"}
            overview.setdefault("environment_line", env_line)

    emotion_snapshot = None
    try:
        emotion_snapshot = load_emotion_cycle_snapshot(fetch_if_missing=True)
    except Exception:
        emotion_snapshot = None

    industry = _resolve_industry(item, diagnose)
    industry_l1 = _lookup_industry_l1(item.ts_code)
    sectors = _load_sector_ranks()
    sector_snapshot = _sector_snapshot(industry, sectors, industry_l1=industry_l1)

    payload: dict[str, Any] = {
        "provider": "zak-market-context-v1",
        "lookback_days": lookback_days,
        "benchmark": {
            "symbol": "000300.SSE",
            "label": BENCHMARK_LABEL,
            f"return_pct_{lookback_days}d": benchmark_pct,
        },
        "stock_vs_benchmark": {
            f"return_pct_{lookback_days}d": stock_pct if isinstance(stock_pct, (int, float)) else None,
            f"benchmark_return_pct_{lookback_days}d": benchmark_pct,
            "excess_pct": excess_pct,
        },
        "market_sentiment": sentiment,
        "sector": sector_snapshot,
        "overview": overview,
    }
    if emotion_snapshot is not None:
        payload["emotion_cycle"] = dump_python(emotion_snapshot)
    payload["summary_lines"] = _build_summary_lines(payload)
    if emotion_snapshot is not None:
        pos_max = int(emotion_snapshot.position_pct_max * 100)
        pos_min = int(emotion_snapshot.position_pct_min * 100)
        if pos_max <= 0:
            pos_text = "建议空仓"
        elif pos_min == pos_max:
            pos_text = f"建议总仓位 {pos_max}%"
        else:
            pos_text = f"建议总仓位 {pos_min}–{pos_max}%"
        allow = "允许新开" if emotion_snapshot.allow_new_positions else "不建议新开"
        payload["summary_lines"].insert(
            0,
            f"情绪周期 {emotion_snapshot.stage_label} · {pos_text} · {allow}",
        )
    if not payload["summary_lines"]:
        payload["note"] = "市场环境数据有限；Chief 可结合终端行情上下文解读大势"
    return payload
