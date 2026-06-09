"""选股筛选 Skill。"""

from __future__ import annotations

import json

from vnpy_skills.base import SkillTemplate, ToolSpec


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
                description=(
                    "解析用户选股意图并生成待确认草案，不会直接执行筛选。"
                    "用户须在确认框中点击「确认运行」后才会执行。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "intent": {
                            "type": "string",
                            "description": "用户原话或归纳后的选股意图",
                        },
                        "preset": {
                            "type": "string",
                            "description": (
                                "内置方案名：涨幅榜/换手率排行/成交量放大/自定义筛选/"
                                "低 PE/中大盘/主力净流入；或留空由系统推断"
                            ),
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
                name="screen_by_condition",
                description=(
                    "【已禁用直接执行】请改用 propose_screening。"
                    "选股须经用户在确认框中确认后才会运行。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "选股条件名"},
                        "top_n": {"type": "integer", "description": "返回前 N 条"},
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
        from vnpy_ashare.screener.nl_mapper import preset_catalog_for_prompt
        from vnpy_ashare.screener.runner import list_all_preset_names

        names = list_all_preset_names(include_saved=True)
        return json.dumps(
            {
                "count": len(names),
                "screeners": names,
                "catalog": preset_catalog_for_prompt(),
                "note": "执行筛选请调用 propose_screening，禁止直接 screen_by_condition。",
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
        from vnpy_ashare.screener.draft_store import save_draft
        from vnpy_ashare.screener.nl_mapper import ProposeInput, try_fast_path, validate_and_build

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
        from vnpy_ashare.screener.presets import get_preset
        from vnpy_ashare.screener.runner import ScreenerRequest, run_screener

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
            summary.append({
                "symbol": r.get("symbol", ""),
                "name": r.get("name", ""),
                "vt_symbol": r.get("vt_symbol", ""),
                "last_price": r.get("last_price"),
                "change_pct": r.get("change_pct"),
                "turnover_rate": r.get("turnover_rate"),
                "pe_ttm": r.get("pe_ttm"),
                "total_mv": r.get("total_mv"),
                "net_mf_amount": r.get("net_mf_amount"),
            })
        return json.dumps(
            {"condition": name, "count": len(summary), "results": summary},
            ensure_ascii=False,
        )

    def screen_by_condition(self, name: str, top_n: int = 10) -> str:
        return json.dumps(
            {
                "status": "blocked",
                "message": (
                    "禁止直接执行选股。请先调用 propose_screening 解析条件，"
                    "并等待用户在确认框中点击「确认运行」。"
                ),
            },
            ensure_ascii=False,
        )
