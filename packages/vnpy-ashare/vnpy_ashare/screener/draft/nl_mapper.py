"""自然语言 / LLM 结构化输出 → ScreenerRequest 草案。

``validate_and_build`` 产出 ``pending_confirm`` 草案供 UI 确认，或 ``need_clarification`` 追问。
"""

from __future__ import annotations

import os
import re
from typing import Literal

from pydantic import Field

from vnpy_ashare.domain.base import MutableModel

from vnpy_ashare.screener.data.quotes_loader import load_market_quote_rows
from vnpy_ashare.screener.draft.draft_store import Confidence, ScreenerDraft, make_draft
from vnpy_ashare.screener.preset.presets import (
    SCREENER_CHANGE_TOP,
    SCREENER_CUSTOM,
    SCREENER_LARGE_CAP,
    SCREENER_LOW_PE,
    SCREENER_MONEYFLOW_IN,
    SCREENER_TURNOVER,
    SCREENER_VOLUME_SURGE,
    get_preset,
    list_builtin_preset_names,
)
from vnpy_ashare.screener.preset.scheme_store import list_schemes
from vnpy_ashare.screener.run.runner import ScreenerRequest, resolve_preset_input

ProposeKind = Literal["pending_confirm", "need_clarification", "error"]

TOP_N_MIN = 1
TOP_N_MAX = 200
TOP_N_DEFAULT = 20


class ProposeInput(MutableModel):
    """LLM propose_screening 工具的结构化输入。"""

    intent: str = Field(description="用户意图描述")
    preset: str = Field(default="", description="preset 名称")
    top_n: int = Field(default=TOP_N_DEFAULT, description="返回条数上限")
    min_change_pct: float | None = Field(default=None, description="最低涨幅（%）")
    max_change_pct: float | None = Field(default=None, description="最高涨幅（%）")
    min_turnover: float | None = Field(default=None, description="最低换手率（%）")
    scheme_name: str | None = Field(default=None, description="已保存方案名称")
    confidence: Confidence = Field(default="medium", description="解析置信度")


class ProposeResult(MutableModel):
    """提案结果：待确认草案 / 需追问 / 错误。"""

    kind: ProposeKind = Field(description="提案结果类型")
    draft: ScreenerDraft | None = Field(default=None, description="待确认草案")
    questions: list[str] | None = Field(default=None, description="追问问题列表")
    message: str = Field(default="", description="错误或提示信息")


_PRESET_ALIASES: dict[str, str] = {
    "涨幅榜": SCREENER_CHANGE_TOP,
    "涨幅": SCREENER_CHANGE_TOP,
    "涨最多": SCREENER_CHANGE_TOP,
    "今天涨": SCREENER_CHANGE_TOP,
    "换手率排行": SCREENER_TURNOVER,
    "换手率": SCREENER_TURNOVER,
    "换手高": SCREENER_TURNOVER,
    "成交量放大": SCREENER_VOLUME_SURGE,
    "放量": SCREENER_VOLUME_SURGE,
    "成交量": SCREENER_VOLUME_SURGE,
    "自定义筛选": SCREENER_CUSTOM,
    "自定义": SCREENER_CUSTOM,
    "低 pe": SCREENER_LOW_PE,
    "低pe": SCREENER_LOW_PE,
    "低估值": SCREENER_LOW_PE,
    "估值低": SCREENER_LOW_PE,
    "中大盘": SCREENER_LARGE_CAP,
    "大盘": SCREENER_LARGE_CAP,
    "大盘股": SCREENER_LARGE_CAP,
    "大票": SCREENER_LARGE_CAP,
    "主力净流入": SCREENER_MONEYFLOW_IN,
    "资金流入": SCREENER_MONEYFLOW_IN,
    "净流入": SCREENER_MONEYFLOW_IN,
}


def clamp_top_n(value: int | None) -> int:
    """将 Top N 限制在 [TOP_N_MIN, TOP_N_MAX]。"""
    if value is None:
        return TOP_N_DEFAULT
    return max(TOP_N_MIN, min(TOP_N_MAX, int(value)))


def normalize_preset_name(name: str) -> str:
    """口语别名 / 内置名 → 标准 preset 名；「我的 · …」原样返回。"""
    key = name.strip()
    if not key:
        return ""
    if key.startswith("我的 · "):
        return key
    lowered = key.lower().replace(" ", "")
    for alias, preset in _PRESET_ALIASES.items():
        if alias.replace(" ", "").lower() == lowered:
            return preset
    if key in list_builtin_preset_names():
        return key
    return key


def build_summary(*, preset_label: str, request: ScreenerRequest) -> str:
    """生成确认框展示的人类可读摘要。"""
    parts = [preset_label, f"Top {request.top_n}"]
    if request.min_change_pct is not None:
        parts.append(f"涨幅 ≥{request.min_change_pct:g}%")
    if request.max_change_pct is not None:
        parts.append(f"涨幅 ≤{request.max_change_pct:g}%")
    if request.min_turnover is not None:
        parts.append(f"换手 ≥{request.min_turnover:g}%")
    return " · ".join(parts)


def collect_warnings(*, source: str) -> list[str]:
    """检查数据源前置条件（TUSHARE_TOKEN / Redis 行情）。"""
    warnings: list[str] = []
    if source == "tushare":
        token = os.getenv("TUSHARE_TOKEN") or os.getenv("TS_TOKEN")
        if not token:
            warnings.append("需要 .env 中配置 TUSHARE_TOKEN，否则无法执行 Tushare 选股。")
    else:
        try:
            load_market_quote_rows()
        except Exception as ex:
            warnings.append(f"Redis 全市场行情不可用（{ex}）。请先运行「工具 → 立即执行 → 行情采集」。")
    return warnings


def _resolve_scheme(scheme_name: str | None) -> tuple[str, ScreenerRequest] | None:
    if not scheme_name or not scheme_name.strip():
        return None
    name = scheme_name.strip()
    for scheme in list_schemes():
        if scheme.name == name:
            label = f"我的 · {scheme.name}"
            top_n = int(scheme.config.get("top_n", TOP_N_DEFAULT) or TOP_N_DEFAULT)
            return label, ScreenerRequest(preset="", top_n=clamp_top_n(top_n), scheme_id=scheme.id)
    return None


def _resolve_request(data: ProposeInput) -> tuple[ScreenerRequest, str, str] | tuple[None, None, str]:
    """返回 (request, preset_label, source) 或 (None, None, error_message)。"""
    scheme = _resolve_scheme(data.scheme_name)
    if data.scheme_name and scheme is None:
        return None, None, f"未找到已保存方案「{data.scheme_name}」"

    if scheme is not None:
        label, request = scheme
        request = ScreenerRequest(
            preset=request.preset,
            top_n=clamp_top_n(data.top_n or request.top_n),
            scheme_id=request.scheme_id,
        )
        for saved in list_schemes():
            if saved.id == request.scheme_id:
                preset_name = str(saved.config.get("preset", ""))
                preset = get_preset(preset_name)
                source = preset.source if preset else "quote"
                break
        else:
            source = "quote"
        return request, label, source

    preset_name = normalize_preset_name(data.preset)
    if not preset_name:
        if data.min_change_pct is not None or data.max_change_pct is not None or data.min_turnover is not None:
            preset_name = SCREENER_CUSTOM
        else:
            return None, None, "未指定选股方案"

    if preset_name.startswith("我的 · "):
        try:
            request = resolve_preset_input(preset_name)
        except ValueError as ex:
            return None, None, str(ex)
        request = ScreenerRequest(
            preset=request.preset,
            top_n=clamp_top_n(data.top_n or request.top_n),
            scheme_id=request.scheme_id,
        )
        return request, preset_name, "quote"

    preset = get_preset(preset_name)
    if preset is None:
        return None, None, f"未知选股方案「{preset_name}」，请调用 list_screeners 查看可用条件"

    request = ScreenerRequest(
        preset=preset.name,
        top_n=clamp_top_n(data.top_n),
        min_change_pct=data.min_change_pct,
        max_change_pct=data.max_change_pct,
        min_turnover=data.min_turnover,
    )
    if preset.name != SCREENER_CUSTOM:
        request = ScreenerRequest(
            preset=preset.name,
            top_n=clamp_top_n(data.top_n),
        )
    return request, preset.name, preset.source


def _clarifying_questions(data: ProposeInput, error: str) -> list[str]:
    questions: list[str] = []
    if error:
        questions.append(error)
    if not data.preset and not data.scheme_name:
        questions.append("您希望按哪种方式筛选？（涨幅榜 / 换手率 / 低 PE / 自定义区间等）")
    if data.confidence == "low":
        questions.append("请补充 Top N 数量或具体阈值（如涨幅、换手率）。")
    return questions


def validate_and_build(data: ProposeInput) -> ProposeResult:
    """校验 LLM 输入并生成待确认草案，或返回追问列表。"""
    if data.confidence == "low":
        questions = _clarifying_questions(data, "")
        return ProposeResult(
            kind="need_clarification",
            questions=questions,
            message="意图不够明确，请先向用户追问后再调用 screen_by_condition 或 run_recipe。",
        )

    resolved = _resolve_request(data)
    if resolved[0] is None:
        questions = _clarifying_questions(data, resolved[2])
        return ProposeResult(
            kind="need_clarification",
            questions=questions,
            message=resolved[2],
        )

    request, preset_label, source = resolved
    summary = build_summary(preset_label=preset_label, request=request)
    warnings = collect_warnings(source=source)
    draft = make_draft(
        natural_language=data.intent.strip(),
        request=request,
        summary=summary,
        preset_label=preset_label,
        source=source,
        confidence=data.confidence,
        warnings=warnings,
    )
    return ProposeResult(
        kind="pending_confirm",
        draft=draft,
        message="已解析选股条件，可直接执行 screen_by_condition。",
    )


def try_fast_path(intent: str) -> ProposeInput | None:
    """关键词预解析：高置信度口语 → 结构化输入。"""
    text = intent.strip()
    if not text:
        return None
    lowered = text.lower().replace(" ", "")

    top_n = TOP_N_DEFAULT
    top_match = re.search(r"(?:前|top)\s*(\d+)", lowered)
    if top_match:
        top_n = clamp_top_n(int(top_match.group(1)))

    min_change: float | None = None
    max_change: float | None = None
    min_turnover: float | None = None

    change_ge = re.search(r"涨幅\s*(?:>|大于|超过|≥|>=)?\s*(\d+(?:\.\d+)?)\s*%?", text)
    if change_ge:
        min_change = float(change_ge.group(1))
    change_le = re.search(r"涨幅\s*(?:<|小于|≤|<=)?\s*(\d+(?:\.\d+)?)\s*%?", text)
    if change_le and min_change is None:
        max_change = float(change_le.group(1))

    turnover_ge = re.search(r"换手\s*(?:>|大于|超过|≥|>=)?\s*(\d+(?:\.\d+)?)\s*%?", text)
    if turnover_ge:
        min_turnover = float(turnover_ge.group(1))

    preset = ""
    confidence: Confidence = "high"

    if min_change is not None or max_change is not None or min_turnover is not None:
        preset = SCREENER_CUSTOM
    elif any(k in lowered for k in ("低pe", "低估值", "估值低")):
        preset = SCREENER_LOW_PE
    elif any(k in text for k in ("主力净流入", "资金流入", "净流入")):
        preset = SCREENER_MONEYFLOW_IN
    elif any(k in text for k in ("中大盘", "大盘股", "大票")):
        preset = SCREENER_LARGE_CAP
    elif any(k in text for k in ("涨幅榜", "涨最多", "今天涨")):
        preset = SCREENER_CHANGE_TOP
    elif "换手" in text:
        preset = SCREENER_TURNOVER
    elif any(k in text for k in ("放量", "成交量放大", "周期资源", "周期")):
        preset = SCREENER_VOLUME_SURGE
    elif any(k in text for k in ("成长赛道", "成长")):
        preset = SCREENER_MONEYFLOW_IN
    elif any(k in text for k in ("长线价投", "价投", "价值投资")):
        preset = SCREENER_LOW_PE
    else:
        return None

    return ProposeInput(
        intent=text,
        preset=preset,
        top_n=top_n,
        min_change_pct=min_change,
        max_change_pct=max_change,
        min_turnover=min_turnover,
        confidence=confidence,
    )


def preset_catalog_for_prompt() -> str:
    """内置 preset + 已保存方案清单，注入 LLM System Prompt。"""
    lines = ["【内置选股方案】"]
    for name in list_builtin_preset_names():
        preset = get_preset(name)
        if preset is None:
            continue
        lines.append(f"- {name}：{preset.description}（数据源 {preset.source}）")
    schemes = list_schemes()
    if schemes:
        lines.append("【已保存方案】")
        for scheme in schemes:
            lines.append(f"- 我的 · {scheme.name}")
    lines.append("自定义区间请用 preset=自定义筛选，并填写 min_change_pct / max_change_pct / min_turnover。")
    return "\n".join(lines)
