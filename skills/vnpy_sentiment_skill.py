"""A 股恐贪指数 Skill。"""

from __future__ import annotations

import json
import os

from dotenv import load_dotenv

from vnpy_common.paths import ENV_FILE
from vnpy_skills.domain.template import SkillTemplate, ToolSpec


class VnpySentimentSkill(SkillTemplate):
    skill_name = "vnpy-sentiment"
    author = "zak"
    description = "A 股择时：恐贪指数与情绪周期，供 AI 自主判断是否写入回答"

    def on_init(self) -> None:
        load_dotenv(ENV_FILE, override=False)
        self._token = os.getenv("TUSHARE_TOKEN") or os.getenv("TS_TOKEN") or ""

    @property
    def available(self) -> bool:
        return bool(self._token)

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="get_ashare_fear_greed_index",
                description=(
                    "查询 A 股全市场恐贪指数（0-100）及分项。"
                    "由你自主判断是否与当前问题相关，无需用户点名「恐贪指数」。"
                    "适合：大盘环境、市场节奏、风险高低、择时背景、综合研判、选股环境。"
                    "不适合：纯个股价格/均线数值、自选增删、回测指标等 factual 问答。"
                    "调用后仅在对结论有增量时再写入正文（通常 1-2 句）；"
                    "指数接近中性且问题不关注大盘时可不写入。"
                ),
                parameters={
                    "type": "object",
                    "properties": {
                        "include_components": {
                            "type": "boolean",
                            "description": "是否返回分项明细，默认 true",
                        },
                        "trade_date": {
                            "type": "string",
                            "description": "交易日 YYYYMMDD，默认最近 A 股交易日",
                        },
                    },
                },
            ),
            ToolSpec(
                name="get_emotion_cycle",
                description=(
                    "查询 A 股短线情绪周期五阶段（冰点/启动/发酵高潮/分歧/退潮）、"
                    "建议总仓位区间、允许模式（打板/半路/低吸）与原始输入计数。"
                    "适合：今天能不能做短线、择时环境、仓位建议、打板/低吸是否合适。"
                    "须引用返回的 inputs 涨跌停数，禁止编造。"
                    "退潮/冰点时须明确不建议短线新开仓。"
                ),
                parameters={"type": "object", "properties": {}},
            ),
        ]

    def _get_sentiment_service(self):
        svc = self._services.get("sentiment")
        if svc is None:
            raise RuntimeError("SentimentService 未就绪")
        return svc

    def get_ashare_fear_greed_index(
        self,
        include_components: bool = True,
        trade_date: str = "",
    ) -> str:
        svc = self._get_sentiment_service()
        snapshot = svc.compute_fear_greed(
            trade_date=trade_date.strip() or None,
            include_components=bool(include_components),
        )
        return json.dumps(
            snapshot.to_dict(include_components=bool(include_components)),
            ensure_ascii=False,
        )

    def get_emotion_cycle(self) -> str:
        from vnpy_ashare.quotes.market.emotion_cycle import load_emotion_cycle_snapshot

        snapshot = load_emotion_cycle_snapshot()
        if snapshot is None:
            return json.dumps(
                {"error": "暂无市场广度数据，请先打开市场页或等待 Redis 行情同步"},
                ensure_ascii=False,
            )
        return json.dumps(snapshot.to_dict(), ensure_ascii=False)
