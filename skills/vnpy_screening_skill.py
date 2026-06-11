"""选股筛选 Skill。"""

from __future__ import annotations

import json

from vnpy_ashare.screener.auto.auto_screen import AutoScreenInput, resolve_auto_screen_request
from vnpy_ashare.screener.draft.nl_mapper import preset_catalog_for_prompt
from vnpy_ashare.screener.pattern.pattern_screen import (
    PatternScreenInput,
    list_pattern_screeners,
    resolve_pattern_screen,
)
from vnpy_ashare.screener.preset.presets import get_preset
from vnpy_ashare.screener.recipe.recipe import list_recipe_catalog
from vnpy_ashare.screener.run.runner import ScreenerRequest, list_all_preset_names, run_screener
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
                name="screen_by_pattern",
                description=(
                    "直接执行 A 股形态选股并返回结果（无需确认）。"
                    "优先通达信问小达 MCP 全市场扫描；MCP 不可用时降级本地日 K（主题投资可降级行情 preset）。"
                    "支持：老鸭头形态/均线多头/W底形态/主题投资。"
                ),
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
                name="screen_by_condition",
                description=(
                    "直接执行选股方案并返回结果。支持内置 preset（涨幅榜/换手率/低PE等）、"
                    "已保存方案（我的 · 方案名）、自定义筛选（须传涨幅/换手阈值）。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "方案名：内置 preset、我的 · 已保存方案名、或「自定义筛选」",
                        },
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
            ToolSpec(
                name="screen_reference_peer",
                description=(
                    "以标杆股为锚，在同业池中按估值接近度与近 5 日动量找同类标的（无需用户确认）。"
                    "相似度 = 同业 40% + 估值 35% + 动量 25%，数据来自 Tushare daily_basic。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "标杆股 vt_symbol，如 600519.SSE",
                        },
                        "top_n": {"type": "integer", "description": "返回前 N 条，默认 20，上限 100"},
                    },
                    "required": ["symbol"],
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
                    "盘中/盘后多因子用 run_recipe；"
                    "内置 preset / 已保存方案 / 自定义筛选用 screen_by_condition；"
                    "形态用 screen_by_pattern；标杆对标用 screen_reference_peer。"
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
                "note": "盘中用 intraday_multi、盘后用 post_close_multi；可先 list_recipes 再 run_recipe。",
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

    def screen_reference_peer(self, symbol: str, top_n: int = 20) -> str:
        vt_symbol = (symbol or "").strip()
        if not vt_symbol:
            return json.dumps({"status": "error", "message": "symbol 不能为空"}, ensure_ascii=False)

        svc = self._get_screening_service()
        try:
            result = svc.run_reference_peer(vt_symbol, top_n=int(top_n or 20))
        except Exception as ex:
            return json.dumps({"status": "error", "message": str(ex)}, ensure_ascii=False)

        if not result.rows:
            return json.dumps(
                {
                    "status": "ok",
                    "reference_vt_symbol": result.reference_vt_symbol,
                    "reference_name": result.reference_name,
                    "reference_industry": result.reference_industry,
                    "trade_date": result.trade_date,
                    "count": 0,
                    "total_scanned": result.total_scanned,
                    "message": f"标杆 {result.reference_name}（{result.reference_industry}）未找到同类标的",
                },
                ensure_ascii=False,
            )

        svc.persist_reference_peer_result(result)
        return json.dumps(
            {
                "status": "ok",
                "reference_vt_symbol": result.reference_vt_symbol,
                "reference_name": result.reference_name,
                "reference_industry": result.reference_industry,
                "trade_date": result.trade_date,
                "count": len(result.rows),
                "total_scanned": result.total_scanned,
                "source": "reference_peer",
                "results": [
                    {
                        "symbol": r.get("symbol", ""),
                        "name": r.get("name", ""),
                        "vt_symbol": r.get("vt_symbol", ""),
                        "similarity_score": r.get("similarity_score"),
                        "hit_reason": r.get("hit_reason"),
                        "pe_ttm": r.get("pe_ttm"),
                        "momentum_5d": r.get("momentum_5d"),
                    }
                    for r in result.rows
                ],
            },
            ensure_ascii=False,
        )
