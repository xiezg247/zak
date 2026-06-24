"""迷你图与笔记保存联动（纯函数）。"""

from __future__ import annotations

import json

from pydantic import ValidationError

from vnpy_common.ai.protocol import AiChartSpec


def format_chart_attachments_appendix(charts: list[AiChartSpec]) -> str:
    """生成可写入分析报告的图表索引 Markdown。"""
    if not charts:
        return ""
    lines = ["---", "", "**附：本轮图表**", ""]
    for spec in charts:
        label = spec.caption or spec.symbol
        kind_label = "K线" if spec.kind == "candlestick" else "折线"
        lines.append(f"- {label}（{kind_label}）")
    return "\n".join(lines)


def merge_report_body_with_charts(body: str, charts: list[AiChartSpec]) -> str:
    text = body.strip()
    appendix = format_chart_attachments_appendix(charts)
    if not appendix:
        return text
    if appendix.strip() in text:
        return text
    return f"{text}\n\n{appendix}" if text else appendix


def parse_charts_from_context_json(context_json: str) -> list[AiChartSpec]:
    """从分析报告 context_json 还原迷你图规格。"""
    text = (context_json or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, dict):
        return []
    raw = payload.get("charts")
    if not isinstance(raw, list):
        return []
    charts: list[AiChartSpec] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            charts.append(AiChartSpec.model_validate(item))
        except ValidationError:
            continue
    return charts
