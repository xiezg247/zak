"""市场摘要预热：情绪周期 + 连板梯队 + 行情行缓存。"""

from __future__ import annotations

from vnpy_ashare.jobs.result import JobResult
from vnpy_ashare.quotes.market.emotion_cycle import classify_emotion_cycle, store_emotion_cycle_snapshot
from vnpy_ashare.quotes.market.emotion_cycle_inputs import build_emotion_cycle_inputs
from vnpy_ashare.quotes.market.limit_ladder_summary import compute_limit_ladder_counts
from vnpy_ashare.quotes.market.market_overview_loaders import _load_breadth
from vnpy_ashare.quotes.market.market_summary_cache import store_limit_ladder_counts
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError, load_market_quote_rows


def warm_market_summary(*, include_ladder: bool = False) -> JobResult:
    """从 Redis 行情计算并写入内存缓存，供 UI / 风控只读。

    - ``include_ladder=False``：仅广度 + 情绪（适合行情采集后轻量预热）
    - ``include_ladder=True``：含连板梯队（耗时长，建议盘后 Tushare 预拉之后）
    """
    try:
        snapshot = load_market_quote_rows(enrich_factors=include_ladder)
    except MarketQuotesLoadError as ex:
        return JobResult(success=True, skipped=True, message=str(ex))

    rows = snapshot.rows
    if not rows:
        return JobResult(success=False, message="Redis 无有效行情行")

    from vnpy_ashare.ai.context.store import set_market_quote_rows_cache

    set_market_quote_rows_cache(rows)

    breadth = _load_breadth(rows, updated_at=snapshot.updated_at)
    if breadth is None:
        return JobResult(success=False, message="无法计算市场广度")

    inputs = build_emotion_cycle_inputs(breadth, include_auxiliary=include_ladder)
    emotion = classify_emotion_cycle(inputs)
    store_emotion_cycle_snapshot(emotion)

    parts = [f"情绪 {emotion.stage_label}", f"扫描 {len(rows)} 只"]
    if include_ladder:
        ladder = compute_limit_ladder_counts(rows)
        store_limit_ladder_counts(ladder)
        total = sum(ladder.values())
        parts.append(f"连板池 {total}")

    return JobResult(success=True, message=" · ".join(parts))
