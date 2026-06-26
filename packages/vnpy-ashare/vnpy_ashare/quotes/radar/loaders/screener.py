"""选股任务缓存卡片加载。"""

from __future__ import annotations

from vnpy_ashare.quotes.radar.loaders.rows import rows_from_screener
from vnpy_ashare.quotes.radar.radar_catalog import DEFAULT_SCREEN_TASK_VARIANT, RadarCardSpec
from vnpy_ashare.quotes.radar.radar_models import RadarCardData, enrich_radar_rows
from vnpy_ashare.screener.run.run_store import ScreenerRunRecord, get_latest_run, is_auto_run, is_strategy_run, list_runs


def detail_page_key_for_run(record) -> str:
    if is_strategy_run(record.config):
        return "screener"
    return "auto_screener"


def run_subtitle(record) -> str:
    summary = str(record.config.get("reason_summary") or record.condition or "").strip()
    parts: list[str] = []
    if record.row_count:
        parts.append(f"共 {record.row_count} 只")
    if summary:
        parts.append(summary)
    return " · ".join(parts)


def card_from_run(
    spec: RadarCardSpec,
    record,
    *,
    empty_message: str,
) -> RadarCardData:
    if record is None or not record.rows:
        return RadarCardData(
            card_id=spec.id,
            title=spec.title,
            subtitle="",
            rows=(),
            empty_message=empty_message,
            updated_at="",
        )
    return RadarCardData(
        card_id=spec.id,
        title=spec.title,
        subtitle=run_subtitle(record),
        rows=enrich_radar_rows(rows_from_screener(record.rows, top_n=spec.top_n)),
        empty_message="",
        updated_at=record.created_at,
        run_id=record.id,
        detail_page_key=detail_page_key_for_run(record),
        total_count=record.row_count,
    )


def find_run_for_task_variant(variant: str) -> ScreenerRunRecord | None:
    if variant == "strategy":
        for record in list_runs(limit=30):
            if is_strategy_run(record.config):
                return record
        return None
    trigger = f"scheduled_{variant.removeprefix('scheduled_')}"
    for record in list_runs(limit=30):
        if not is_auto_run(record.config):
            continue
        if str(record.config.get("trigger", "")) == trigger:
            return record
    return None


def load_screen_task(spec: RadarCardSpec, *, variant: str = DEFAULT_SCREEN_TASK_VARIANT) -> RadarCardData:
    if variant == "latest":
        return card_from_run(
            spec,
            get_latest_run(),
            empty_message="暂无选股记录，请前往「策略选股」或「自动选股」运行。",
        )
    record = find_run_for_task_variant(variant)
    label = {
        "scheduled_intraday": "盘中定时任务",
        "scheduled_post_close": "盘后定时任务",
        "strategy": "策略选股",
    }.get(variant, variant)
    empty = f"暂无「{label}」运行记录。"
    return card_from_run(spec, record, empty_message=empty)
