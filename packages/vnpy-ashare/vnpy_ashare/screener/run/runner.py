"""选股统一执行入口（GUI / CLI / Skill 共用）。

数据流::

    ScreenerRequest → data_source（Redis / Tushare fallback）→ rules → ScreenerRunResult

``scheme_id`` 非空时优先走已保存方案，忽略 ``preset``。
"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_ashare.domain.base import MutableModel
from vnpy_ashare.screener.data.data_source import (
    enrich_recipe_rows,
    fetch_fundamental_screening_rows,
    fetch_limit_list_with_fallback,
    fetch_moneyflow_with_fallback,
    load_screening_quote_snapshot,
)
from vnpy_ashare.screener.data.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.preset.presets import (
    SCHEME_KIND_INDUSTRY,
    SCREENER_CUSTOM,
    PresetDefinition,
    get_preset,
    list_builtin_preset_names,
)
from vnpy_ashare.screener.preset.rules import (
    apply_large_cap,
    apply_limit_up,
    apply_low_pe,
    apply_moneyflow_in,
    apply_quote_preset,
)
from vnpy_ashare.screener.preset.scheme_store import SavedScheme, get_scheme, list_schemes
from vnpy_ashare.screener.run.export import resolve_export_columns
from vnpy_ashare.screener.run.industry_screen import run_industry_screen
from vnpy_ashare.screener.run.result import ScreenerRunResult


class ScreenerRequest(MutableModel):
    """选股请求；``scheme_id`` 非空时走已保存方案。"""

    preset: str = Field(description="内置 preset 名称")
    top_n: int = Field(default=20, description="返回条数上限")
    min_change_pct: float | None = Field(default=None, description="最低涨幅（%）")
    max_change_pct: float | None = Field(default=None, description="最高涨幅（%）")
    min_turnover: float | None = Field(default=None, description="最低换手率（%）")
    scheme_id: str | None = Field(default=None, description="已保存方案 id")


def run_screener(request: ScreenerRequest) -> ScreenerRunResult:
    """执行选股：行情 preset 走 Redis/Tushare 快照，基本面 preset 走 Tushare。"""
    if request.scheme_id:
        scheme = get_scheme(request.scheme_id)
        if scheme is None:
            raise ValueError(f"选股方案不存在：{request.scheme_id}")
        return _run_from_scheme(scheme, top_n=request.top_n)

    preset = get_preset(request.preset)
    if preset is None:
        raise ValueError(f"未知选股方案：{request.preset}")

    if preset.source == "quote":
        try:
            snapshot = load_screening_quote_snapshot()
        except MarketQuotesLoadError as ex:
            raise RuntimeError(str(ex)) from ex
        rows = apply_quote_preset(
            preset.name,
            snapshot.rows,
            top_n=request.top_n,
            min_change_pct=request.min_change_pct,
            max_change_pct=request.max_change_pct,
            min_turnover=request.min_turnover,
        )
        rows = enrich_recipe_rows(rows)
        return ScreenerRunResult(
            rows=rows,
            condition=preset.name,
            updated_at=snapshot.updated_at,
            total_scanned=snapshot.total,
            source=snapshot.source,
            columns=resolve_export_columns(rows),
        )

    return _run_tushare_preset(preset, top_n=request.top_n)


def _run_from_scheme(scheme: SavedScheme, *, top_n: int) -> ScreenerRunResult:
    config = dict(scheme.config)
    if str(config.get("kind") or "") == SCHEME_KIND_INDUSTRY:

        industry = str(config.get("industry") or "").strip()
        if not industry:
            raise ValueError(f"方案「{scheme.name}」缺少行业字段")
        effective_top_n = max(1, min(int(config.get("top_n", top_n) or top_n), 200))
        result = run_industry_screen(industry, top_n=effective_top_n)
        result.condition = f"我的方案 · {scheme.name}"
        return result

    preset_name = str(config.get("preset", ""))
    merged = ScreenerRequest(
        preset=preset_name,
        top_n=int(config.get("top_n", top_n) or top_n),
        min_change_pct=config.get("min_change_pct"),
        max_change_pct=config.get("max_change_pct"),
        min_turnover=config.get("min_turnover"),
    )
    result = run_screener(merged)
    result.condition = f"我的方案 · {scheme.name}"
    return result


def _run_tushare_preset(preset: PresetDefinition, *, top_n: int) -> ScreenerRunResult:
    top_n = max(1, min(int(top_n or 20), 200))

    if preset.rule_kind == "moneyflow_in":
        raw_rows, trade_date = fetch_moneyflow_with_fallback()
        if not raw_rows:
            raise RuntimeError("Tushare moneyflow 在最近多个交易日均无数据，请稍后重试或检查积分权限。")
        rows = apply_moneyflow_in(raw_rows, top_n=top_n)
        return ScreenerRunResult(
            rows=rows,
            condition=preset.name,
            updated_at=trade_date,
            total_scanned=len(raw_rows),
            source="tushare",
            columns=resolve_export_columns(rows),
        )

    if preset.rule_kind == "limit_up":
        raw_rows, trade_date = fetch_limit_list_with_fallback(limit_type="U")
        if not raw_rows:
            raise RuntimeError("Tushare 涨停列表在最近多个交易日均无数据，请稍后重试或检查积分权限。")
        rows = apply_limit_up(raw_rows, top_n=top_n)
        return ScreenerRunResult(
            rows=rows,
            condition=preset.name,
            updated_at=trade_date,
            total_scanned=len(raw_rows),
            source="tushare",
            columns=resolve_export_columns(rows),
        )

    raw_rows, trade_date, source_tag = fetch_fundamental_screening_rows()

    if preset.rule_kind == "low_pe":
        rows = apply_low_pe(raw_rows, top_n=top_n)
    elif preset.rule_kind == "large_cap":
        rows = apply_large_cap(raw_rows, top_n=top_n)
    else:
        raise ValueError(f"未实现的 Tushare 方案：{preset.name}")

    return ScreenerRunResult(
        rows=rows,
        condition=preset.name,
        updated_at=trade_date,
        total_scanned=len(raw_rows),
        source=source_tag,
        columns=resolve_export_columns(rows),
    )


def build_scheme_config(request: ScreenerRequest) -> dict[str, Any]:
    """将请求序列化为方案持久化 config。"""
    return {
        "preset": request.preset,
        "top_n": request.top_n,
        "min_change_pct": request.min_change_pct,
        "max_change_pct": request.max_change_pct,
        "min_turnover": request.min_turnover,
    }


def build_industry_scheme_config(industry: str, *, top_n: int) -> dict[str, Any]:
    """行业成分方案 config。"""
    label = (industry or "").strip()
    if not label:
        raise ValueError("行业名称不能为空")
    return {
        "kind": SCHEME_KIND_INDUSTRY,
        "industry": label,
        "top_n": max(1, min(int(top_n or 20), 200)),
    }


def list_all_preset_names(*, include_saved: bool = True) -> list[str]:
    """列出内置 preset 名称；``include_saved`` 时追加「我的 · …」方案。"""
    names = list_builtin_preset_names()
    if include_saved:
        for scheme in list_schemes():
            names.append(f"我的 · {scheme.name}")
    return names


def resolve_preset_input(preset_label: str) -> ScreenerRequest:
    """将 UI / LLM 展示的 preset 标签解析为 ``ScreenerRequest``。"""
    label = preset_label.strip()
    if label.startswith("我的 · "):
        scheme_name = label.removeprefix("我的 · ").strip()

        for scheme in list_schemes():
            if scheme.name == scheme_name:
                return ScreenerRequest(preset="", top_n=20, scheme_id=scheme.id)
        raise ValueError(f"未找到已保存方案：{scheme_name}")

    if label == SCREENER_CUSTOM:
        return ScreenerRequest(preset=label)
    return ScreenerRequest(preset=label)
