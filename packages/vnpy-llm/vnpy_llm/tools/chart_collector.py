"""从工具 JSON 结果提取 AI 聊天迷你图规格。"""

from __future__ import annotations

import json
import uuid
from typing import Any

from vnpy_common.ai.protocol import AiChartBar, AiChartSpec

MAX_CHART_BARS = 60
MAX_ATTACHMENTS_PER_TURN = 5
CHART_TOOL_KINDS: dict[str, str] = {
    "get_bars_data": "candlestick",
    "technical_snapshot": "candlestick",
    "get_backtest_result": "line",
    "analyze_financial": "line",
    "explain_screening_run": "candlestick",
    "get_screening_context": "candlestick",
}
MAX_SCREENING_CHARTS = 3
DEFAULT_MA_OVERLAYS: list[dict[str, object]] = [
    {"kind": "ma", "period": 5},
    {"kind": "ma", "period": 20},
]
_LINE_COLORS = {
    "pe": "#5b9cf5",
    "pb": "#c9a227",
    "equity": "#5b9cf5",
}


def attachment_key(spec: AiChartSpec) -> str:
    return spec.chart_key or spec.symbol


def _scope_label(scope: str) -> str:
    cleaned = (scope or "daily").strip().lower()
    if cleaned == "1m":
        return "1分钟"
    return "日K"


def _build_caption(*, symbol: str, scope: str, count: int, suffix: str = "本地数据") -> str:
    return f"{symbol} · 近{count}根{_scope_label(scope)} · {suffix}"


def _parse_bars(rows: list[Any]) -> list[AiChartBar]:
    bars: list[AiChartBar] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date = str(row.get("date") or "").strip()
        if not date:
            continue
        try:
            bars.append(
                AiChartBar(
                    date=date,
                    open=float(row.get("open", 0)),
                    high=float(row.get("high", 0)),
                    low=float(row.get("low", 0)),
                    close=float(row.get("close", 0)),
                    volume=int(row.get("volume") or 0),
                )
            )
        except (TypeError, ValueError):
            continue
    return bars[-MAX_CHART_BARS:]


def _parse_line_points(rows: list[Any]) -> list[AiChartBar]:
    points: list[AiChartBar] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date = str(row.get("date") or "").strip()
        if not date:
            continue
        raw_value = row.get("value")
        if raw_value is None:
            raw_value = row.get("close", 0)
        if not isinstance(raw_value, (int, float, str)):
            continue
        try:
            value = float(raw_value)
        except ValueError:
            continue
        points.append(
            AiChartBar(
                date=date,
                open=value,
                high=value,
                low=value,
                close=value,
                volume=0,
            )
        )
    return points[-MAX_CHART_BARS:]


def _line_overlays(color_key: str) -> list[dict[str, object]]:
    color = _LINE_COLORS.get(color_key, _LINE_COLORS["equity"])
    return [{"kind": "line_style", "color": color}]


def _build_candlestick_spec(
    *,
    tool_name: str,
    symbol: str,
    scope: str,
    series: list[AiChartBar],
    name: str = "",
    caption: str = "",
    overlays: list[dict[str, object]] | None = None,
) -> AiChartSpec | None:
    if not series:
        return None
    return AiChartSpec(
        chart_id=uuid.uuid4().hex[:12],
        kind="candlestick",
        symbol=symbol,
        chart_key=symbol,
        name=name,
        scope=scope,
        caption=caption or _build_caption(symbol=symbol, scope=scope, count=len(series)),
        series=series,
        overlays=list(overlays or DEFAULT_MA_OVERLAYS),
        source_tool=tool_name,
    )


def _build_line_spec(
    *,
    tool_name: str,
    symbol: str,
    chart_key: str,
    series: list[AiChartBar],
    caption: str,
    name: str = "",
    color_key: str = "equity",
) -> AiChartSpec | None:
    if not series:
        return None
    return AiChartSpec(
        chart_id=uuid.uuid4().hex[:12],
        kind="line",
        symbol=symbol,
        chart_key=chart_key,
        name=name,
        caption=caption,
        series=series,
        overlays=_line_overlays(color_key),
        source_tool=tool_name,
    )


def _collect_get_bars_data(payload: dict[str, Any], tool_name: str) -> list[AiChartSpec]:
    symbol = str(payload.get("symbol") or "").strip()
    if not symbol:
        return []
    rows = payload.get("data")
    if not isinstance(rows, list):
        return []
    series = _parse_bars(rows)
    scope = str(payload.get("scope") or "daily")
    spec = _build_candlestick_spec(tool_name=tool_name, symbol=symbol, scope=scope, series=series)
    return [spec] if spec is not None else []


def _collect_technical_snapshot(payload: dict[str, Any], tool_name: str) -> list[AiChartSpec]:
    if payload.get("warnings"):
        return []
    symbol = str(payload.get("symbol") or "").strip()
    if not symbol:
        return []
    rows = payload.get("chart_series")
    if not isinstance(rows, list):
        return []
    series = _parse_bars(rows)
    scope = str(payload.get("scope") or "daily")
    name = str(payload.get("name") or "")
    caption = _build_caption(symbol=symbol, scope=scope, count=len(series), suffix="技术面")
    spec = _build_candlestick_spec(
        tool_name=tool_name,
        symbol=symbol,
        scope=scope,
        series=series,
        name=name,
        caption=caption,
    )
    return [spec] if spec is not None else []


def _collect_backtest_equity(payload: dict[str, Any], tool_name: str) -> list[AiChartSpec]:
    rows = payload.get("equity_curve")
    if not isinstance(rows, list) or not rows:
        return []
    series = _parse_line_points(rows)
    if not series:
        return []
    vt_symbol = str(payload.get("vt_symbol") or payload.get("symbol") or "回测").strip()
    strategy = str(payload.get("strategy") or "策略").strip()
    chart_key = f"backtest:{vt_symbol}"
    spec = _build_line_spec(
        tool_name=tool_name,
        symbol=vt_symbol,
        chart_key=chart_key,
        series=series,
        caption=f"{strategy} · {vt_symbol} · 权益曲线",
        color_key="equity",
    )
    return [spec] if spec is not None else []


def _collect_analyze_financial(payload: dict[str, Any], tool_name: str) -> list[AiChartSpec]:
    symbol = str(payload.get("symbol") or "").strip()
    if not symbol:
        return []
    name = str(payload.get("name") or "")
    title = name or symbol
    specs: list[AiChartSpec] = []

    pe_rows = payload.get("valuation_pe_series")
    if isinstance(pe_rows, list) and pe_rows:
        pe_series = _parse_line_points(pe_rows)
        pe_spec = _build_line_spec(
            tool_name=tool_name,
            symbol=symbol,
            chart_key=f"valuation:pe:{symbol}",
            series=pe_series,
            caption=f"{title} · PE(TTM) 近{len(pe_series)}日",
            name=name,
            color_key="pe",
        )
        if pe_spec is not None:
            specs.append(pe_spec)

    pb_rows = payload.get("valuation_pb_series")
    if isinstance(pb_rows, list) and pb_rows:
        pb_series = _parse_line_points(pb_rows)
        pb_spec = _build_line_spec(
            tool_name=tool_name,
            symbol=symbol,
            chart_key=f"valuation:pb:{symbol}",
            series=pb_series,
            caption=f"{title} · PB 近{len(pb_series)}日",
            name=name,
            color_key="pb",
        )
        if pb_spec is not None:
            specs.append(pb_spec)

    return specs


def _collect_screening_batch(payload: dict[str, Any], tool_name: str) -> list[AiChartSpec]:
    if payload.get("message") and not payload.get("count"):
        return []
    batch = payload.get("batch_snapshots")
    if not isinstance(batch, list):
        return []
    specs: list[AiChartSpec] = []
    for item in batch[:MAX_SCREENING_CHARTS]:
        if not isinstance(item, dict):
            continue
        if item.get("warnings"):
            continue
        symbol = str(item.get("vt_symbol") or "").strip()
        rows = item.get("chart_series")
        if not symbol or not isinstance(rows, list) or not rows:
            continue
        series = _parse_bars(rows)
        name = str(item.get("name") or "")
        title = name or symbol
        spec = _build_candlestick_spec(
            tool_name=tool_name,
            symbol=symbol,
            scope="daily",
            series=series,
            name=name,
            caption=f"{title} · 选股Top · 近{len(series)}日",
        )
        if spec is not None:
            specs.append(spec)
    return specs


_COLLECTORS: dict[str, Any] = {
    "get_bars_data": _collect_get_bars_data,
    "technical_snapshot": _collect_technical_snapshot,
    "get_backtest_result": _collect_backtest_equity,
    "analyze_financial": _collect_analyze_financial,
    "explain_screening_run": _collect_screening_batch,
    "get_screening_context": _collect_screening_batch,
}


def try_collect_charts(tool_name: str, result: str, *, success: bool) -> list[AiChartSpec]:
    """解析工具结果，返回 0..N 张迷你图规格。"""
    if not success or tool_name not in CHART_TOOL_KINDS:
        return []
    text = (result or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict) or payload.get("error"):
        return []
    if payload.get("message") and tool_name == "get_backtest_result" and not payload.get("equity_curve"):
        return []

    collector = _COLLECTORS.get(tool_name)
    if collector is None:
        return []
    return [spec for spec in collector(payload, tool_name) if spec is not None]


def try_collect_chart(tool_name: str, result: str, *, success: bool) -> AiChartSpec | None:
    charts = try_collect_charts(tool_name, result, success=success)
    return charts[0] if charts else None


def merge_chart_attachment(attachments: list[AiChartSpec], spec: AiChartSpec) -> list[AiChartSpec]:
    """同 chart_key 去重，保留最新一张图。"""
    key = attachment_key(spec)
    kept = [item for item in attachments if attachment_key(item) != key]
    kept.append(spec)
    return kept[-MAX_ATTACHMENTS_PER_TURN:]
