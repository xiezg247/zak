"""雷达盘面与极致短线选股 Skill。"""

from __future__ import annotations

import json

from vnpy_ashare.screener.run.short_term_screen import run_short_term_screen
from vnpy_skills.domain.template import SkillTemplate, ToolSpec


class VnpyRadarSkill(SkillTemplate):
    skill_name = "vnpy-radar"
    author = "zak"
    description = "雷达盘面快照、龙头选股与极致短线编排"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_radar_snapshot",
                description="读取雷达全页快照（情绪阶段、共振、龙头、连板梯队摘要）；需先在雷达页刷新",
                parameters={
                    "type": "object",
                    "properties": {},
                },
            ),
            ToolSpec(
                name="get_leader_pick_snapshot",
                description="读取雷达「选股·龙头」卡当前候选（不写入选股历史）",
                parameters={
                    "type": "object",
                    "properties": {
                        "variant": {
                            "type": "string",
                            "enum": ["mainline", "all_market"],
                            "description": "主线 mainline / 全市场 all_market，默认 mainline",
                        },
                        "top_n": {"type": "integer", "description": "返回前 N 条，默认 12"},
                    },
                },
            ),
            ToolSpec(
                name="run_leader_screen",
                description=("按 leader_score 执行雷达龙头选股（硬过滤 + 情绪周期 gate）。退潮/冰点返回空结果；variant 可选 mainline 或 all_market。"),
                parameters={
                    "type": "object",
                    "properties": {
                        "top_n": {"type": "integer", "description": "返回前 N 条，默认 12"},
                        "variant": {
                            "type": "string",
                            "enum": ["mainline", "all_market"],
                            "description": "主线龙头 mainline / 全市场龙头 all_market",
                        },
                    },
                },
            ),
            ToolSpec(
                name="run_short_term_screen",
                description=("极致短线编排：情绪 gate → 龙头池 → 可选共振交集 → 可选主池过滤 → 落库。适用于「抓龙头」「短线主池」「共振票」等意图。"),
                parameters={
                    "type": "object",
                    "properties": {
                        "top_n": {"type": "integer", "description": "返回前 N 条，默认 12"},
                        "variant": {
                            "type": "string",
                            "enum": ["mainline", "all_market"],
                            "description": "龙头 variant，默认 mainline",
                        },
                        "require_resonance": {
                            "type": "boolean",
                            "description": "是否与雷达共振≥2卡取交集，默认 false",
                        },
                        "ultra_short_only": {
                            "type": "boolean",
                            "description": "是否收窄至短线主池，默认 true",
                        },
                    },
                },
            ),
        ]

    def _get_screening_service(self):
        svc = self._services.get("screening")
        if svc is None:
            raise RuntimeError("ScreeningService 未就绪")
        return svc

    def _get_radar_service(self):
        svc = self._services.get("radar")
        if svc is None:
            raise RuntimeError("RadarService 未就绪")
        return svc

    def get_radar_snapshot(self) -> str:
        radar = self._get_radar_service()
        payload = radar.snapshot_to_dict()
        return json.dumps(payload, ensure_ascii=False)

    def run_leader_screen(self, top_n: int = 12, variant: str = "mainline") -> str:
        svc = self._get_screening_service()
        variant_key = (variant or "mainline").strip().lower()
        if variant_key not in ("mainline", "all_market"):
            variant_key = "mainline"
        try:
            result = svc.run_leader_screen(top_n=int(top_n or 12), variant=variant_key)
        except Exception as ex:
            return json.dumps({"status": "error", "message": str(ex)}, ensure_ascii=False)

        config = {"trigger": "radar_leader", "leader_variant": variant_key}
        if result.rows:
            svc.persist_run_result(result, trigger="radar_leader", extra_config=config)

        return self._format_screen_result(result, variant=variant_key)

    def run_short_term_screen(
        self,
        top_n: int = 12,
        variant: str = "mainline",
        require_resonance: bool = False,
        ultra_short_only: bool = True,
    ) -> str:
        svc = self._get_screening_service()
        variant_key = (variant or "mainline").strip().lower()
        if variant_key not in ("mainline", "all_market"):
            variant_key = "mainline"
        try:
            result = run_short_term_screen(
                top_n=int(top_n or 12),
                variant=variant_key,
                require_resonance=bool(require_resonance),
                ultra_short_only=bool(ultra_short_only),
            )
        except Exception as ex:
            return json.dumps({"status": "error", "message": str(ex)}, ensure_ascii=False)

        config = {
            "trigger": "short_term",
            "leader_variant": variant_key,
            "require_resonance": bool(require_resonance),
            "ultra_short_only": bool(ultra_short_only),
        }
        if result.rows:
            svc.persist_run_result(result, trigger="short_term", extra_config=config)

        return self._format_screen_result(
            result,
            variant=variant_key,
            require_resonance=bool(require_resonance),
            ultra_short_only=bool(ultra_short_only),
        )

    def get_leader_pick_snapshot(self, variant: str = "mainline", top_n: int = 12) -> str:
        from vnpy_ashare.quotes.radar.radar_catalog import list_radar_cards
        from vnpy_ashare.quotes.radar.radar_leader_pick import load_leader_pick

        variant_key = (variant or "mainline").strip().lower()
        if variant_key not in ("mainline", "all_market"):
            variant_key = "mainline"
        spec = next((item for item in list_radar_cards() if item.id == "leader_pick"), None)
        if spec is None:
            return json.dumps({"status": "error", "message": "leader_pick 卡片未注册"}, ensure_ascii=False)

        card = load_leader_pick(spec, variant=variant_key)  # type: ignore[arg-type]
        rows = list(card.rows)[: max(1, int(top_n or 12))]
        return json.dumps(
            {
                "status": "ok",
                "variant": variant_key,
                "subtitle": card.subtitle,
                "count": len(rows),
                "total_count": card.total_count,
                "results": [
                    {
                        "symbol": r.symbol,
                        "name": r.name,
                        "vt_symbol": r.vt_symbol,
                        "leader_score": r.leader_score,
                        "leader_tier": r.leader_tier,
                        "limit_times": r.limit_times,
                        "change_pct": r.change_pct,
                    }
                    for r in rows
                ],
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _format_screen_result(
        result,
        *,
        variant: str = "mainline",
        require_resonance: bool = False,
        ultra_short_only: bool = False,
    ) -> str:
        return json.dumps(
            {
                "status": "ok",
                "condition": result.condition,
                "count": len(result.rows),
                "source": result.source,
                "updated_at": result.updated_at,
                "total_scanned": result.total_scanned,
                "variant": variant,
                "require_resonance": require_resonance,
                "ultra_short_only": ultra_short_only,
                "results": [
                    {
                        "symbol": r.get("symbol", ""),
                        "name": r.get("name", ""),
                        "vt_symbol": r.get("vt_symbol", ""),
                        "leader_score": r.get("leader_score"),
                        "leader_tier": r.get("leader_tier"),
                        "leader_tier_label": r.get("leader_tier_label"),
                        "limit_times": r.get("limit_times"),
                        "hit_reason": r.get("hit_reason"),
                        "change_pct": r.get("change_pct"),
                    }
                    for r in result.rows
                ],
            },
            ensure_ascii=False,
        )
