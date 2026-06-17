"""以标杆股为锚，在全市场找同类标的（同业 + 估值 + 走势）。

相似度 = 同业 40% + 估值接近 35% + 近 5 日动量 25%；数据来自 Tushare daily_basic。
"""

from __future__ import annotations

import math
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv

from vnpy_ashare.domain.datetime import format_china_datetime
from vnpy_ashare.integrations.tushare import TushareNotConfiguredError
from vnpy_ashare.integrations.tushare.factors import fetch_daily_pct_map, fetch_stock_industry_map
from vnpy_ashare.quotes.core.quote_rows import quote_rows_by_vt_symbol
from vnpy_ashare.screener.data.data_source import fetch_daily_basic_with_fallback, iter_trade_date_strs
from vnpy_common.paths import ENV_FILE

ProgressCallback = Callable[[str], None]
CancelledCallback = Callable[[], bool]
DEFAULT_TOP_N = 20
REFERENCE_PEER_TOP_N_MAX = 100
_MOMENTUM_DAYS = 5
_WEIGHT_INDUSTRY = 0.40
_WEIGHT_VALUATION = 0.35
_WEIGHT_MOMENTUM = 0.25


class ReferencePeerCancelled(Exception):
    """用户关闭弹窗或请求中断。"""


def clamp_reference_peer_top_n(value: int | None) -> int:
    """Top N 限制在 [1, REFERENCE_PEER_TOP_N_MAX]。"""
    try:
        number = int(value if value is not None else DEFAULT_TOP_N)
    except (TypeError, ValueError):
        number = DEFAULT_TOP_N
    return max(1, min(number, REFERENCE_PEER_TOP_N_MAX))


def env_default_reference_peer_top_n() -> int:
    """从 .env REFERENCE_PEER_TOP_N 读取默认 Top N。"""



    load_dotenv(ENV_FILE)
    raw = os.getenv("REFERENCE_PEER_TOP_N", "").strip()
    if not raw:
        return DEFAULT_TOP_N
    try:
        return clamp_reference_peer_top_n(int(raw))
    except ValueError:
        return DEFAULT_TOP_N


@dataclass
class ReferencePeerRunResult:
    """标杆对标选股结果（含步骤日志）。"""

    reference_vt_symbol: str
    reference_name: str
    reference_industry: str
    trade_date: str
    rows: list[dict[str, Any]]
    steps: list[str] = field(default_factory=list)
    total_scanned: int = 0


def run_reference_peer_screen(
    vt_symbol: str,
    *,
    reference_name: str = "",
    top_n: int = DEFAULT_TOP_N,
    on_progress: ProgressCallback | None = None,
    cancelled: CancelledCallback | None = None,
) -> ReferencePeerRunResult:
    """以 vt_symbol 为标杆，在同业池中按估值+动量打分取 top_n。

    ``on_progress`` 推送步骤文案；``cancelled`` 返回 True 时抛 ReferencePeerCancelled。
    """
    steps: list[str] = []

    def progress(message: str) -> None:
        steps.append(message)
        if on_progress is not None:
            on_progress(message)

    def check_cancelled() -> None:
        if cancelled is not None and cancelled():
            raise ReferencePeerCancelled

    vt_symbol = vt_symbol.strip()
    if not vt_symbol:
        raise ValueError("缺少标杆股 vt_symbol")

    check_cancelled()
    progress("正在加载全市场基本面与行业分类…")
    fund_rows, trade_date = fetch_daily_basic_with_fallback()
    if not fund_rows:
        raise RuntimeError("暂无基本面数据，请检查 TUSHARE_TOKEN 或稍后重试")

    check_cancelled()
    industry_map = fetch_stock_industry_map()
    by_symbol = quote_rows_by_vt_symbol(fund_rows)

    reference = by_symbol.get(vt_symbol)
    if reference is None:
        raise RuntimeError(f"未找到标杆股 {vt_symbol} 的基本面数据")

    ref_industry = _resolve_industry(reference, industry_map)
    ref_name = reference_name or str(reference.get("name") or vt_symbol)
    progress(f"标杆：{ref_name} · 行业 {ref_industry or '未知'}")

    if not ref_industry or ref_industry == "未知":
        raise RuntimeError("标杆股缺少行业分类，暂无法做同业对标")

    candidates = [row for row in fund_rows if str(row.get("vt_symbol")) != vt_symbol and _resolve_industry(row, industry_map) == ref_industry]
    progress(f"同业池 {len(candidates)} 只，拉取近 {_MOMENTUM_DAYS} 日涨跌幅…")
    if not candidates:
        return ReferencePeerRunResult(
            reference_vt_symbol=vt_symbol,
            reference_name=ref_name,
            reference_industry=ref_industry,
            trade_date=trade_date,
            rows=[],
            steps=steps,
            total_scanned=len(fund_rows),
        )

    pct_maps: list[dict[str, float]] = []
    for day in list(iter_trade_date_strs(max_lookback=_MOMENTUM_DAYS)):
        check_cancelled()
        pct_maps.append(fetch_daily_pct_map(day))
        if len(pct_maps) >= _MOMENTUM_DAYS:
            break

    ref_ts = str(reference.get("ts_code", ""))
    ref_momentum = _cumulative_return(ref_ts, pct_maps)
    ref_pe = _positive_float(reference.get("pe_ttm") or reference.get("pe"))
    ref_mv = _positive_float(reference.get("circ_mv") or reference.get("total_mv"))

    progress("正在计算估值接近度与走势相似度…")
    scored: list[dict[str, Any]] = []
    for row in candidates:
        check_cancelled()
        ts_code = str(row.get("ts_code", ""))
        val_score = _valuation_score(
            pe=_positive_float(row.get("pe_ttm") or row.get("pe")),
            mv=_positive_float(row.get("circ_mv") or row.get("total_mv")),
            ref_pe=ref_pe,
            ref_mv=ref_mv,
        )
        cand_momentum = _cumulative_return(ts_code, pct_maps)
        mom_score = _momentum_score(ref_momentum, cand_momentum)
        industry_score = 100.0
        composite = round(
            industry_score * _WEIGHT_INDUSTRY + val_score * _WEIGHT_VALUATION + mom_score * _WEIGHT_MOMENTUM,
            1,
        )
        reasons = [
            f"同业：{ref_industry}",
            _valuation_reason(row, ref_pe=ref_pe, ref_mv=ref_mv),
            f"近{_MOMENTUM_DAYS}日涨跌 {cand_momentum:+.2f}%（标杆 {ref_momentum:+.2f}%）",
        ]
        scored.append(
            {
                "symbol": row.get("symbol", ""),
                "name": row.get("name", ""),
                "vt_symbol": row.get("vt_symbol", ""),
                "reference_vt_symbol": vt_symbol,
                "similarity_score": composite,
                "hit_reason": reasons[0] if len(reasons) == 1 else "；".join(reasons[:2]),
                "hit_reasons": reasons,
                "industry": ref_industry,
                "pe_ttm": row.get("pe_ttm") or row.get("pe") or 0,
                "circ_mv": row.get("circ_mv") or row.get("total_mv") or 0,
                "momentum_5d": round(cand_momentum, 2),
                "source": "reference_peer",
            }
        )

    scored.sort(
        key=lambda item: (float(item.get("similarity_score") or 0),),
        reverse=True,
    )
    rows = scored[: clamp_reference_peer_top_n(top_n)]
    progress(f"完成，命中 {len(rows)} 条同类标的")
    now = format_china_datetime()
    for row in rows:
        row["updated_at"] = now

    return ReferencePeerRunResult(
        reference_vt_symbol=vt_symbol,
        reference_name=ref_name,
        reference_industry=ref_industry,
        trade_date=trade_date,
        rows=rows,
        steps=steps,
        total_scanned=len(candidates),
    )


def _resolve_industry(row: dict[str, Any], industry_map: dict[str, str]) -> str:
    ts_code = str(row.get("ts_code", ""))
    industry = industry_map.get(ts_code, "").strip()
    return industry or "未知"


def _positive_float(value: Any) -> float:
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def _cumulative_return(ts_code: str, pct_maps: list[dict[str, float]]) -> float:
    if not ts_code:
        return 0.0
    compound = 1.0
    for mapping in pct_maps:
        pct = float(mapping.get(ts_code, 0) or 0)
        compound *= 1.0 + pct / 100.0
    return (compound - 1.0) * 100.0


def _valuation_score(*, pe: float, mv: float, ref_pe: float, ref_mv: float) -> float:
    parts: list[float] = []
    if pe > 0 and ref_pe > 0:
        parts.append(min(abs(math.log(pe) - math.log(ref_pe)), 2.0) / 2.0)
    if mv > 0 and ref_mv > 0:
        parts.append(min(abs(math.log(mv) - math.log(ref_mv)), 2.0) / 2.0)
    if not parts:
        return 50.0
    distance = sum(parts) / len(parts)
    return round(max(0.0, (1.0 - distance) * 100), 1)


def _momentum_score(reference: float, candidate: float) -> float:
    diff = abs(reference - candidate)
    return round(max(0.0, 100.0 - min(diff, 40.0) * 2.5), 1)


def _valuation_reason(row: dict[str, Any], *, ref_pe: float, ref_mv: float) -> str:
    pe = _positive_float(row.get("pe_ttm") or row.get("pe"))
    mv = _positive_float(row.get("circ_mv") or row.get("total_mv"))
    pe_text = f"PE {pe:.1f}" if pe > 0 else "PE —"
    mv_text = f"流通市值 {mv:,.0f} 万" if mv > 0 else "市值 —"
    ref_pe_text = f"{ref_pe:.1f}" if ref_pe > 0 else "—"
    ref_mv_text = f"{ref_mv:,.0f}" if ref_mv > 0 else "—"
    return f"估值：{pe_text} / {mv_text}（标杆 PE {ref_pe_text} · 流通市值 {ref_mv_text} 万）"


__all__ = [
    "ReferencePeerCancelled",
    "ReferencePeerRunResult",
    "TushareNotConfiguredError",
    "clamp_reference_peer_top_n",
    "env_default_reference_peer_top_n",
    "run_reference_peer_screen",
]
