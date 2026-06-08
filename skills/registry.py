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
}


def format_skills_prompt(enabled: list[str]) -> str:
    """兼容 LlmEngine：实际 prompt 由 SkillEngine.build_skills_prompt() 生成。"""
    if not enabled:
        return ""
    lines = ["【已启用 Skills】"]
    for name in enabled:
        meta = OFFICIAL_SKILLS.get(name)
        if meta:
            lines.append(f"- {meta.title}（{name}）：{meta.summary}")
        else:
            lines.append(f"- {name}（自编写 Python Skill）")
    return "\n".join(lines)
