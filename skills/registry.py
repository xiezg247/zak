"""技能元数据（Agent Skill + 自编写 Python Skill）。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SkillMeta:
    skill_name: str
    title: str
    summary: str
    source: str
    tags: tuple[str, ...]


# 官方 Agent Skills（由 scripts/sync_skills.py 同步）
OFFICIAL_SKILLS: dict[str, SkillMeta] = {
    "tushare-data": SkillMeta(
        skill_name="tushare-data",
        title="Tushare 数据研究",
        summary="220+ 金融数据接口，支持财报、估值、资金流、宏观等自然语言查询。",
        source="https://github.com/waditu-tushare/skills",
        tags=("基本面", "财务", "宏观", "Tushare"),
    ),
    "tickflow": SkillMeta(
        skill_name="tickflow",
        title="TickFlow 行情",
        summary="A 股/港股/美股实时行情、K 线、财务数据（TickFlow Python SDK）。",
        source="https://github.com/tickflow-org/tickflow-skills",
        tags=("行情", "K 线", "实时", "TickFlow"),
    ),
    "vnpy-context": SkillMeta(
        skill_name="vnpy-context",
        title="终端上下文",
        summary="自选池、本地 K 线概览、当前选中标的、最近回测摘要。",
        source="zak",
        tags=("自选", "本地 K 线", "回测", "终端"),
    ),
    "vnpy-sentiment": SkillMeta(
        skill_name="vnpy-sentiment",
        title="A 股恐贪指数",
        summary="全市场恐贪指数（0-100）及分项，供 AI 自主判断是否写入回答。",
        source="zak",
        tags=("情绪", "大盘", "Tushare", "恐贪"),
    ),
    "tdx-stock-picker": SkillMeta(
        skill_name="tdx-stock-picker",
        title="通达信 AI 选股",
        summary="利用通达信 MCP 行情/财务/技术指标/板块/研报工具进行多条件 A 股筛选。",
        source="zak",
        tags=("选股", "通达信", "MCP", "A 股"),
    ),
    "tdx-stock-diagnose": SkillMeta(
        skill_name="tdx-stock-diagnose",
        title="通达信个股诊断",
        summary="问小达 MCP 综合诊断：行情、MACD/KDJ/RSI、PE/ROE、主力资金、研报。",
        source="zak",
        tags=("诊断", "通达信", "MCP", "A 股"),
    ),
}
