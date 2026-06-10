"""选股筛选 Skill。"""

from __future__ import annotations

import json

from vnpy_ashare.screener.auto_screen import AutoScreenInput, resolve_auto_screen_request
from vnpy_ashare.screener.draft_store import save_draft
from vnpy_ashare.screener.nl_mapper import (
    ProposeInput,
    preset_catalog_for_prompt,
    try_fast_path,
    validate_and_build,
)
from vnpy_ashare.screener.pattern_screen import (
    PatternScreenInput,
    list_pattern_screeners,
    resolve_pattern_screen,
)
from vnpy_ashare.screener.presets import get_preset
from vnpy_ashare.screener.recipe import list_recipe_catalog
from vnpy_ashare.screener.recipe_draft_store import save_recipe_draft
from vnpy_ashare.screener.recipe_nl_mapper import ProposeRecipeInput, validate_and_build_recipe
from vnpy_ashare.screener.runner import ScreenerRequest, list_all_preset_names, run_screener
from vnpy_skills.domain import SkillTemplate, ToolSpec


class VnpyScreeningSkill(SkillTemplate):
    skill_name = "vnpy-screening"
    author = "zak"
    description = "按条件筛选标的（涨幅榜、换手率、成交量等）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="list_screeners",
                description="列出所有可用的选股条件（内置方案与已保存方案）",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="propose_screening",
                description=("解析用户选股意图并生成待确认草案，不会直接执行筛选。用户须在确认框中点击「确认运行」后才会执行。"),
                parameters={
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "description": "用户原话或归纳后的选股意图",
                        },
                        "preset": {
                            "type": "string",
                            "description": ("内置方案名：涨幅榜/换手率排行/成交量放大/自定义筛选/低 PE/中大盘/主力净流入；或留空由系统推断"),
                        },
                        "top_n": {
                            "type": "integer",
                            "description": "返回前 N 条，默认 20，上限 200",
                        },
                        "min_change_pct": {
                            "type": "number",
                            "description": "最小涨幅（%），仅自定义筛选",
                        },
                        "max_change_pct": {
                            "type": "number",
                            "description": "最大涨幅（%），仅自定义筛选",
                        },
                        "min_turnover": {
                            "type": "number",
                            "description": "最小换手率（%），仅自定义筛选",
                        },
                        "scheme_name": {
                            "type": "string",
                            "description": "已保存方案名称（不含「我的 · 」前缀）",
                        },
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "解析置信度；low 时不创建草案，应追问用户",
                        },
                    },
                    "required": ["intent"],
                },
            ),
            ToolSpec(
                name="screen_by_pattern",
                description=("直接执行 A 股形态选股并返回结果（无需确认）。支持：老鸭头形态/均线多头/W底形态/主题投资。依赖本地日 K（主题投资需全市场行情）。"),
                parameters={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "形态名称，如 老鸭头形态、均线多头、W底形态、主题投资",
                        },
                        "top_n": {"type": "integer", "description": "返回前 N 条，默认 20"},
                    },
                    "required": ["pattern"],
                },
            ),
            ToolSpec(
                name="list_recipes",
                description="列出多因子选股配方（内置与用户保存）；可按 trigger_kind 过滤盘中/盘后",
                parameters={
                    "type": "object",
                    "properties": {
                        "trigger_kind": {
                            "type": "string",
                            "enum": ["intraday", "post_close", ""],
                            "description": "可选：intraday 盘中 / post_close 盘后；留空返回全部",
                        },
                    },
                },
            ),
            ToolSpec(
                name="run_recipe",
                description=("直接执行多因子选股配方并返回结果（无需用户确认）。适用于盘中多因子、盘后多因子等意图明确的场景。"),
                parameters={
                    "type": "object",
                    "properties": {
                        "recipe_id": {
                            "type": "string",
                            "description": "配方 id，如 intraday_multi、post_close_multi；可先 list_recipes",
                        },
                        "top_n": {"type": "integer", "description": "返回前 N 条，默认 20"},
                    },
                    "required": ["recipe_id"],
                },
            ),
            ToolSpec(
                name="propose_recipe",
                description=("解析用户多因子选股意图并生成待确认配方草案，不会直接执行。复杂或自定义配方时使用；意图明确时优先 run_recipe。"),
                parameters={
                    "type": "object",
                    "properties": {
                        "intent": {"type": "string", "description": "用户原话或归纳后的选股意图"},
                        "trigger_kind": {
                            "type": "string",
                            "enum": ["intraday", "post_close", ""],
                            "description": "可选触发类型；留空则从 intent 推断",
                        },
                        "recipe_id": {
                            "type": "string",
                            "description": "指定配方 id；留空则从 intent 匹配内置配方",
                        },
                        "top_n": {"type": "integer", "description": "返回前 N 条，默认 20"},
                        "confidence": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "解析置信度；low 时不创建草案",
                        },
                    },
                    "required": ["intent"],
                },
            ),
            ToolSpec(
                name="screen_by_condition",
                description=(
                    "直接执行内置选股方案并返回结果（无需用户确认）。适用于涨幅榜/换手率/低PE等内置 preset；已保存方案或复杂条件请改用 propose_screening。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "内置选股方案名"},
                        "top_n": {"type": "integer", "description": "返回前 N 条，默认 20"},
                        "min_change_pct": {
                            "type": "number",
                            "description": "最小涨幅（%），仅自定义筛选",
                        },
                        "max_change_pct": {
                            "type": "number",
                            "description": "最大涨幅（%），仅自定义筛选",
                        },
                        "min_turnover": {
                            "type": "number",
                            "description": "最小换手率（%），仅自定义筛选",
                        },
                    },
                    "required": ["name"],
                },
            ),
        ]

    def _get_screening_service(self):
        svc = self._services.get("screening")
        if svc is None:
            raise RuntimeError("ScreeningService 未就绪")
        return svc

    def list_screeners(self) -> str:
        names = list_all_preset_names(include_saved=True)
        return json.dumps(
            {
                "count": len(names),
                "screeners": names,
                "patterns": list_pattern_screeners(),
                "catalog": preset_catalog_for_prompt(),
                "note": (
                    "盘中/盘后多因子用 run_recipe 或 propose_recipe；"
                    "内置 preset 用 screen_by_condition；形态用 screen_by_pattern；"
                    "复杂/保存方案用 propose_screening。"
                ),
                "recipes": [
                    {
                        "recipe_id": entry.recipe_id,
                        "display_name": entry.display_name,
                        "trigger_kind": entry.trigger_kind,
                    }
                    for entry in list_recipe_catalog()
                ],
            },
            ensure_ascii=False,
        )

    def list_recipes(self, trigger_kind: str = "") -> str:
        kind = (trigger_kind or "").strip().lower()
        if kind and kind not in ("intraday", "post_close"):
            kind = ""
        catalog = list_recipe_catalog(trigger_kind=kind or None)
        return json.dumps(
            {
                "count": len(catalog),
                "trigger_kind": kind or "all",
                "recipes": [
                    {
                        "recipe_id": entry.recipe_id,
                        "display_name": entry.display_name,
                        "trigger_kind": entry.trigger_kind,
                        "builtin": entry.builtin,
                    }
                    for entry in catalog
                ],
                "note": "意图明确时 run_recipe(recipe_id)；复杂条件 propose_recipe(intent)。",
            },
            ensure_ascii=False,
        )

    def run_recipe(self, recipe_id: str, top_n: int = 20) -> str:
        rid = (recipe_id or "").strip()
        if not rid:
            return json.dumps({"status": "error", "message": "recipe_id 不能为空"}, ensure_ascii=False)

        svc = self._get_screening_service()
        try:
            result = svc.run_recipe(rid, top_n=int(top_n or 20), condition_prefix="AI")
        except Exception as ex:
            return json.dumps({"status": "error", "message": str(ex)}, ensure_ascii=False)

        if not result.rows:
            return json.dumps(
                {
                    "status": "ok",
                    "recipe_id": rid,
                    "condition": result.condition,
                    "count": 0,
                    "total_scanned": result.total_scanned,
                    "message": f"配方「{result.condition}」未命中标的（已扫描约 {result.total_scanned} 只）",
                },
                ensure_ascii=False,
            )

        svc.persist_run_result(result, nl_source=f"recipe:{rid}")
        return json.dumps(
            {
                "status": "ok",
                "recipe_id": rid,
                "condition": result.condition,
                "count": len(result.rows),
                "source": result.source,
                "updated_at": result.updated_at,
                "total_scanned": result.total_scanned,
                "results": [
                    {
                        "symbol": r.get("symbol", ""),
                        "name": r.get("name", ""),
                        "vt_symbol": r.get("vt_symbol", ""),
                        "composite_score": r.get("composite_score"),
                        "hit_reason": r.get("hit_reason"),
                        "dimensions": r.get("dimensions"),
                        "change_pct": r.get("change_pct"),
                        "turnover_rate": r.get("turnover_rate"),
                        "volume_ratio": r.get("volume_ratio"),
                    }
                    for r in result.rows
                ],
            },
            ensure_ascii=False,
        )

    def propose_recipe(
        self,
        intent: str,
        trigger_kind: str = "",
        recipe_id: str = "",
        top_n: int = 20,
        confidence: str = "medium",
    ) -> str:
        intent_text = (intent or "").strip()
        if not intent_text:
            return json.dumps({"status": "error", "message": "intent 不能为空"}, ensure_ascii=False)

        conf = confidence if confidence in ("high", "medium", "low") else "medium"
        result = validate_and_build_recipe(
            ProposeRecipeInput(
                intent=intent_text,
                trigger_kind=trigger_kind or "",
                recipe_id=recipe_id or "",
                top_n=top_n,
                confidence=conf,  # type: ignore[arg-type]
            )
        )
        if result.kind == "need_clarification":
            return json.dumps(
                {
                    "status": "need_clarification",
                    "questions": result.questions or [],
                    "message": result.message,
                },
                ensure_ascii=False,
            )
        if result.kind == "error" or result.draft is None:
            return json.dumps(
                {"status": "error", "message": result.message or "无法生成配方草案"},
                ensure_ascii=False,
            )

        save_recipe_draft(result.draft)
        return json.dumps(
            {
                "status": "pending_confirm",
                "draft_id": result.draft.id,
                "recipe_id": result.draft.recipe_id,
                "trigger_kind": result.draft.trigger_kind,
                "summary": result.draft.summary,
                "top_n": result.draft.top_n,
                "confidence": result.draft.confidence,
                "message": result.message,
            },
            ensure_ascii=False,
        )

    def propose_screening(
        self,
        intent: str,
        preset: str = "",
        top_n: int = 20,
        min_change_pct: float | None = None,
        max_change_pct: float | None = None,
        min_turnover: float | None = None,
        scheme_name: str | None = None,
        confidence: str = "medium",
    ) -> str:
        intent_text = (intent or "").strip()
        if not intent_text:
            return json.dumps(
                {"status": "error", "message": "intent 不能为空"},
                ensure_ascii=False,
            )

        conf = confidence if confidence in ("high", "medium", "low") else "medium"
        data = ProposeInput(
            intent=intent_text,
            preset=preset or "",
            top_n=top_n,
            min_change_pct=min_change_pct,
            max_change_pct=max_change_pct,
            min_turnover=min_turnover,
            scheme_name=scheme_name,
            confidence=conf,  # type: ignore[arg-type]
        )

        if not preset and not scheme_name and conf != "low":
            fast = try_fast_path(intent_text)
            if fast is not None:
                data = fast

        result = validate_and_build(data)
        if result.kind == "need_clarification":
            return json.dumps(
                {
                    "status": "need_clarification",
                    "questions": result.questions or [],
                    "message": result.message,
                },
                ensure_ascii=False,
            )
        if result.kind == "error" or result.draft is None:
            return json.dumps(
                {"status": "error", "message": result.message or "无法生成草案"},
                ensure_ascii=False,
            )

        save_draft(result.draft)
        return json.dumps(
            {
                "status": "pending_confirm",
                "draft_id": result.draft.id,
                "summary": result.draft.summary,
                "preset": result.draft.preset_label,
                "source": result.draft.source,
                "warnings": result.draft.warnings,
                "confidence": result.draft.confidence,
                "message": result.message,
            },
            ensure_ascii=False,
        )

    def run_screener(self, name: str, top_n: int = 10) -> str:
        preset = get_preset(name)
        if preset is not None and preset.source == "tushare":
            try:
                result = run_screener(ScreenerRequest(preset=name, top_n=int(top_n or 10)))
                return self._format_results(name, result.rows)
            except Exception as ex:
                return json.dumps({"message": str(ex)}, ensure_ascii=False)

        svc = self._get_screening_service()
        try:
            results = svc.screen_quote_preset(name, top_n=int(top_n or 10))
        except RuntimeError as ex:
            return json.dumps({"message": str(ex)}, ensure_ascii=False)
        if not results:
            return json.dumps(
                {
                    "message": f"选股条件「{name}」未匹配到标的，可用的条件见 list_screeners",
                    "count": 0,
                },
                ensure_ascii=False,
            )
        return self._format_results(name, results)

    def _format_results(self, name: str, results: list[dict]) -> str:
        summary = []
        for r in results:
            summary.append(
                {
                    "symbol": r.get("symbol", ""),
                    "name": r.get("name", ""),
                    "vt_symbol": r.get("vt_symbol", ""),
                    "last_price": r.get("last_price"),
                    "change_pct": r.get("change_pct"),
                    "turnover_rate": r.get("turnover_rate"),
                    "pe_ttm": r.get("pe_ttm"),
                    "total_mv": r.get("total_mv"),
                    "net_mf_amount": r.get("net_mf_amount"),
                }
            )
        return json.dumps(
            {"condition": name, "count": len(summary), "results": summary},
            ensure_ascii=False,
        )

    def screen_by_pattern(self, pattern: str, top_n: int = 20) -> str:
        pattern_id, error = resolve_pattern_screen(PatternScreenInput(pattern=pattern, top_n=top_n))
        if error:
            return json.dumps({"status": "error", "message": error}, ensure_ascii=False)

        svc = self._get_screening_service()
        try:
            result = svc.run_pattern_screen(pattern, top_n=int(top_n or 20))
        except Exception as ex:
            return json.dumps({"status": "error", "message": str(ex)}, ensure_ascii=False)

        if not result.rows:
            return json.dumps(
                {
                    "status": "ok",
                    "pattern": pattern_id,
                    "condition": result.condition,
                    "count": 0,
                    "total_scanned": result.total_scanned,
                    "message": f"形态「{result.condition}」未匹配到标的（已扫描 {result.total_scanned} 只本地日 K）",
                },
                ensure_ascii=False,
            )

        svc.persist_run_result(result, nl_source=f"pattern:{pattern_id}")
        return json.dumps(
            {
                "status": "ok",
                "pattern": pattern_id,
                "condition": result.condition,
                "count": len(result.rows),
                "source": result.source,
                "updated_at": result.updated_at,
                "total_scanned": result.total_scanned,
                "results": [
                    {
                        "symbol": r.get("symbol", ""),
                        "name": r.get("name", ""),
                        "vt_symbol": r.get("vt_symbol", ""),
                        "last_price": r.get("last_price"),
                        "change_pct": r.get("change_pct"),
                        "pattern_score": r.get("pattern_score"),
                        "pattern_hint": r.get("pattern_hint"),
                    }
                    for r in result.rows
                ],
            },
            ensure_ascii=False,
        )

    def screen_by_condition(
        self,
        name: str,
        top_n: int = 20,
        min_change_pct: float | None = None,
        max_change_pct: float | None = None,
        min_turnover: float | None = None,
    ) -> str:
        resolved = resolve_auto_screen_request(
            AutoScreenInput(
                name=name,
                top_n=top_n,
                min_change_pct=min_change_pct,
                max_change_pct=max_change_pct,
                min_turnover=min_turnover,
            )
        )
        if resolved.need_confirm:
            return json.dumps(
                {
                    "status": "need_confirm",
                    "message": resolved.error or "请改用 propose_screening 生成草案并等待用户确认。",
                },
                ensure_ascii=False,
            )
        if not resolved.ok or resolved.request is None:
            return json.dumps(
                {"status": "error", "message": resolved.error or "无法执行选股"},
                ensure_ascii=False,
            )

        svc = self._get_screening_service()
        try:
            result = svc.run_request(resolved.request)
        except Exception as ex:
            return json.dumps({"status": "error", "message": str(ex)}, ensure_ascii=False)

        if not result.rows:
            return json.dumps(
                {
                    "status": "ok",
                    "condition": result.condition,
                    "count": 0,
                    "message": f"选股条件「{result.condition}」未匹配到标的",
                },
                ensure_ascii=False,
            )

        svc.persist_run_result(result, nl_source=f"auto:{name}")
        return json.dumps(
            {
                "status": "ok",
                "condition": result.condition,
                "count": len(result.rows),
                "source": result.source,
                "updated_at": result.updated_at,
                "total_scanned": result.total_scanned,
                "results": [
                    {
                        "symbol": r.get("symbol", ""),
                        "name": r.get("name", ""),
                        "vt_symbol": r.get("vt_symbol", ""),
                        "last_price": r.get("last_price"),
                        "change_pct": r.get("change_pct"),
                        "turnover_rate": r.get("turnover_rate"),
                        "pe_ttm": r.get("pe_ttm"),
                        "total_mv": r.get("total_mv"),
                        "net_mf_amount": r.get("net_mf_amount"),
                    }
                    for r in result.rows
                ],
            },
            ensure_ascii=False,
        )
