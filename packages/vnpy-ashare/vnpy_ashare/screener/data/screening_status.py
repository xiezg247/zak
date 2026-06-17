"""选股页数据状态与运行洞察（纯函数，供 UI / Worker 共用）。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pydantic import Field

from vnpy_ashare.domain.screener.result_row import ScreeningRowLike
from vnpy_ashare.domain.time.market_hours import ashare_market_phase_label, is_ashare_trading_session
from vnpy_ashare.quotes.core.redis_store import RedisQuoteStore
from vnpy_ashare.screener.data.data_source import resolve_result_source_tag
from vnpy_ashare.screener.data.quote_freshness import ensure_fresh_quotes_for_screening, quote_snapshot_age_seconds
from vnpy_ashare.screener.preset.presets import get_preset
from vnpy_ashare.screener.preset.scheme_store import get_scheme
from vnpy_ashare.screener.recipe.recipe import ScreenRecipe, TriggerKind, resolve_recipe
from vnpy_ashare.screener.run.runner import resolve_preset_input
from vnpy_ashare.screener.sector.sector_summary import attach_industry, compute_sector_distribution
from vnpy_common.domain.base import FrozenModel


class ScreeningDataStatus(FrozenModel):
    """选股页顶部数据状态快照。"""

    phase: str = Field(description="当前市场阶段标签")
    trading: bool = Field(description="是否处于交易时段")
    expected_source: str = Field(description="预期行情数据来源")
    quote_age_seconds: float | None = Field(description="行情快照年龄（秒）")
    quote_updated_at: str | None = Field(description="行情快照更新时间")

    @property
    def can_refresh_quotes(self) -> bool:
        return self.trading

    def summary_line(self) -> str:
        parts = [self.phase]
        if self.trading:
            parts.append("交易时段")
            if self.quote_age_seconds is not None:
                parts.append(f"Redis {int(self.quote_age_seconds)} 秒前")
            elif self.quote_updated_at:
                parts.append(f"Redis · {self.quote_updated_at}")
            else:
                parts.append("Redis 暂无快照")
        else:
            parts.append("非交易时段")
            parts.append(f"行情类将用 {self.expected_source} 日频回退")
        return " · ".join(parts)


def build_screening_data_status(*, uses_live_quotes: bool = True) -> ScreeningDataStatus:
    """构建当前数据状态（不触发采集）。"""
    trading = is_ashare_trading_session()
    store = RedisQuoteStore()
    updated_at = store.get_updated_at()
    age = quote_snapshot_age_seconds()
    expected = resolve_result_source_tag("tushare") if not trading else resolve_result_source_tag("redis")
    if not uses_live_quotes and trading:
        expected = resolve_result_source_tag("tushare")
    return ScreeningDataStatus(
        phase=ashare_market_phase_label(),
        trading=trading,
        expected_source=expected,
        quote_age_seconds=age,
        quote_updated_at=str(updated_at).strip() if updated_at else None,
    )


def preset_uses_live_quotes(preset_name: str) -> bool:
    preset = get_preset((preset_name or "").strip())
    if preset is None:
        return False
    return preset.source == "quote"


def request_uses_live_quotes(
    *,
    preset: str = "",
    scheme_id: str | None = None,
) -> bool:
    """策略选股请求是否会走 Redis 实时行情。"""
    if scheme_id:
        scheme = get_scheme(scheme_id)
        if scheme is not None:
            if str(scheme.config.get("kind") or "") == "industry":
                return True
            saved_preset = str(scheme.config.get("preset") or "")
            if saved_preset:
                return preset_uses_live_quotes(saved_preset)
        return True

    label = (preset or "").strip()
    if label.startswith("我的 · "):
        resolved = resolve_preset_input(label)
        return preset_uses_live_quotes(resolved.preset)
    return preset_uses_live_quotes(label)


def recipe_uses_live_quotes(recipe: ScreenRecipe | None) -> bool:
    if recipe is None:
        return False
    return recipe.trigger_kind == "intraday"


def prepare_quotes_for_screening(*, uses_live_quotes: bool) -> tuple[bool, str]:
    """运行前确保行情足够新；非实时类或非交易时段跳过。"""
    if not uses_live_quotes:
        return True, ""
    if not is_ashare_trading_session():
        return True, ""
    return ensure_fresh_quotes_for_screening()


def resolve_run_trigger_kind(config: dict[str, Any] | None) -> TriggerKind | None:
    """从 run config 推断盘中/盘后，供侧栏过滤。"""
    if not config:
        return None
    trigger = str(config.get("trigger", ""))
    if trigger == "scheduled_intraday":
        return "intraday"
    if trigger == "scheduled_post_close":
        return "post_close"
    explicit = str(config.get("trigger_kind", "")).strip()
    if explicit in ("intraday", "post_close"):
        return explicit  # type: ignore[return-value]
    recipe_id = str(config.get("recipe_id") or "").strip()
    if recipe_id:
        recipe = resolve_recipe(recipe_id)
        if recipe is not None:
            return recipe.trigger_kind
    return None


def format_diff_insight(config: dict[str, Any] | None) -> str:
    """格式化 run_diff 摘要行。"""
    if not config:
        return ""
    diff = config.get("run_diff")
    if not isinstance(diff, dict):
        return ""
    new_count = int(diff.get("new_count") or 0)
    stay_count = int(diff.get("stay_count") or 0)
    drop_count = int(diff.get("drop_count") or 0)
    if new_count == 0 and stay_count == 0 and drop_count == 0:
        return ""
    return f"较上次：新增 {new_count} · 保留 {stay_count} · 剔除 {drop_count}"


def format_sector_insight(rows: Sequence[ScreeningRowLike], *, top_n: int = 5) -> str:
    """格式化行业分布摘要行。"""
    if not rows:
        return ""
    enriched = attach_industry(rows)
    stats = compute_sector_distribution(enriched, top_n=top_n, min_stocks=1)
    if not stats:
        return ""
    parts = [f"{item['industry']}({item['count']}只/{float(item['avg_change_pct']):+.2f}%)" for item in stats[:top_n]]
    return "行业分布：" + " · ".join(parts)


def build_run_insight_detail(
    rows: Sequence[ScreeningRowLike],
    config: dict[str, Any] | None = None,
) -> str:
    """合并 diff + 板块洞察，写入运行输出 detail。"""
    lines = [line for line in (format_diff_insight(config), format_sector_insight(rows)) if line]
    return "\n".join(lines)
