"""选股统一执行入口（GUI / CLI / Skill 共用）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from vnpy_ashare.screener.data_source import (
    fetch_fundamental_screening_rows,
    fetch_moneyflow_with_fallback,
    load_screening_quote_snapshot,
)
from vnpy_ashare.screener.export import resolve_export_columns
from vnpy_ashare.screener.presets import SCREENER_CUSTOM, PresetDefinition, get_preset
from vnpy_ashare.screener.quotes_loader import MarketQuotesLoadError
from vnpy_ashare.screener.rules import (
    apply_large_cap,
    apply_low_pe,
    apply_moneyflow_in,
    apply_quote_preset,
)
from vnpy_ashare.screener.scheme_store import SavedScheme, get_scheme


@dataclass
class ScreenerRunResult:
    rows: list[dict[str, Any]]
    condition: str
    updated_at: str | None
    total_scanned: int
    source: str
    columns: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class ScreenerRequest:
    preset: str
    top_n: int = 20
    min_change_pct: float | None = None
    max_change_pct: float | None = None
    min_turnover: float | None = None
    scheme_id: str | None = None


def run_screener(request: ScreenerRequest) -> ScreenerRunResult:
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
    return {
        "preset": request.preset,
        "top_n": request.top_n,
        "min_change_pct": request.min_change_pct,
        "max_change_pct": request.max_change_pct,
        "min_turnover": request.min_turnover,
    }


def list_all_preset_names(*, include_saved: bool = True) -> list[str]:
    from vnpy_ashare.screener.presets import list_builtin_preset_names
    from vnpy_ashare.screener.scheme_store import list_schemes

    names = list_builtin_preset_names()
    if include_saved:
        for scheme in list_schemes():
            names.append(f"我的 · {scheme.name}")
    return names


def resolve_preset_input(preset_label: str) -> ScreenerRequest:
    label = preset_label.strip()
    if label.startswith("我的 · "):
        scheme_name = label.removeprefix("我的 · ").strip()
        from vnpy_ashare.screener.scheme_store import list_schemes

        for scheme in list_schemes():
            if scheme.name == scheme_name:
                return ScreenerRequest(preset="", top_n=20, scheme_id=scheme.id)
        raise ValueError(f"未找到已保存方案：{scheme_name}")

    if label == SCREENER_CUSTOM:
        return ScreenerRequest(preset=label)
    return ScreenerRequest(preset=label)
