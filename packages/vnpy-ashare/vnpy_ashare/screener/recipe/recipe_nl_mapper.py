"""自然语言 → 配方草案。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import timedelta

from vnpy_ashare.domain.datetime import china_now, format_china_datetime
from typing import Literal

from vnpy_ashare.screener.recipe.recipe import (
    RECIPE_INTRADAY_MULTI,
    RECIPE_POST_CLOSE_MULTI,
    TriggerKind,
    list_recipe_catalog,
    resolve_recipe,
)
from vnpy_ashare.screener.recipe.recipe_draft_store import Confidence, RecipeDraft, create_draft_id

ProposeRecipeKind = Literal["pending_confirm", "need_clarification", "error"]

TOP_N_MIN = 1
TOP_N_MAX = 200
TOP_N_DEFAULT = 20


@dataclass
class ProposeRecipeInput:
    intent: str
    trigger_kind: str = ""
    recipe_id: str = ""
    top_n: int = TOP_N_DEFAULT
    confidence: Confidence = "medium"


@dataclass
class ProposeRecipeResult:
    kind: ProposeRecipeKind
    draft: RecipeDraft | None = None
    questions: list[str] | None = None
    message: str = ""


_INTRADAY_HINTS = (
    "盘中",
    "现在",
    "当下",
    "实时",
    "今天异动",
    "午盘",
    "早盘",
    "尾盘",
    "短线游资",
    "游资",
    "题材",
    "连板",
    "涨停",
    "热点",
)
_POST_CLOSE_HINTS = (
    "盘后",
    "收盘",
    "估值",
    "资金流入",
    "低pe",
    "低 pe",
    "基本面",
    "中线波段",
    "波段",
    "中线",
)
_STYLE_INTRADAY_RECIPE = ("短线游资", "游资", "题材活跃", "连板", "涨停", "热点")
_STYLE_POST_CLOSE_RECIPE = ("中线波段", "波段", "中线")


def validate_and_build_recipe(data: ProposeRecipeInput) -> ProposeRecipeResult:
    intent = (data.intent or "").strip()
    if not intent:
        return ProposeRecipeResult(kind="error", message="intent 不能为空")

    if data.confidence == "low":
        return ProposeRecipeResult(
            kind="need_clarification",
            questions=["请说明要盘中选股还是盘后选股？关注动量、量比、换手还是估值资金？"],
            message="置信度较低，需追问用户",
        )

    trigger = _resolve_trigger_kind(intent, data.trigger_kind)
    recipe_id = (data.recipe_id or "").strip() or _resolve_recipe_id(intent, trigger)
    recipe = resolve_recipe(recipe_id)
    if recipe is None:
        catalog = list_recipe_catalog(trigger_kind=trigger)
        names = [entry.display_name for entry in catalog[:6]]
        return ProposeRecipeResult(
            kind="need_clarification",
            questions=[
                f"未识别配方，请从以下选择或说明维度组合：{', '.join(names) or '内置盘中/盘后多因子'}",
            ],
            message=f"未知配方：{recipe_id}",
        )

    top_n = max(TOP_N_MIN, min(int(data.top_n or TOP_N_DEFAULT), TOP_N_MAX))
    dims = " + ".join(spec.label for spec in recipe.dimensions)
    summary = f"{recipe.name}（{dims}）Top {top_n}"
    now = china_now()
    expires = now + timedelta(minutes=10)

    draft = RecipeDraft(
        id=create_draft_id(),
        natural_language=intent,
        recipe_id=recipe.recipe_id,
        trigger_kind=recipe.trigger_kind,
        top_n=top_n,
        summary=summary,
        confidence=data.confidence,
        warnings=[],
        status="pending",
        created_at=format_china_datetime(now),
        expires_at=format_china_datetime(expires),
    )
    return ProposeRecipeResult(
        kind="pending_confirm",
        draft=draft,
        message=f"已解析配方「{summary}」，可直接执行 run_recipe(recipe_id={recipe.recipe_id})",
    )


def _resolve_trigger_kind(intent: str, explicit: str) -> TriggerKind:
    explicit = (explicit or "").strip().lower()
    if explicit in ("intraday", "盘中"):
        return "intraday"
    if explicit in ("post_close", "盘后"):
        return "post_close"
    lower = intent.lower()
    if any(hint in lower for hint in _INTRADAY_HINTS):
        return "intraday"
    if any(hint in lower for hint in _POST_CLOSE_HINTS):
        return "post_close"
    return "intraday"


def _resolve_recipe_id(intent: str, trigger: TriggerKind) -> str:
    if any(k in intent for k in _STYLE_INTRADAY_RECIPE):
        return RECIPE_INTRADAY_MULTI
    if any(k in intent for k in _STYLE_POST_CLOSE_RECIPE):
        return RECIPE_POST_CLOSE_MULTI

    lower = intent.lower()
    for entry in list_recipe_catalog(trigger_kind=trigger):
        rid = entry.recipe_id
        name_part = entry.display_name.replace("内置 · ", "").replace("我的 · ", "")
        if name_part and name_part in intent:
            return rid
        if rid in lower:
            return rid

    if trigger == "intraday":
        if re.search(r"多因子|综合|增强", lower):
            return RECIPE_INTRADAY_MULTI
        return RECIPE_INTRADAY_MULTI
    return RECIPE_POST_CLOSE_MULTI
