"""交易体系 Playbook AI 上下文与快捷动作。"""

from __future__ import annotations

from vnpy_ashare.domain.trading.playbook import HomePlaybookStatus
from vnpy_ashare.services.trading_playbook import load_playbook_sections
from vnpy_common.ai.protocol import QuickAction


def build_playbook_extra(status: HomePlaybookStatus | None = None) -> str:
    """拼装 Playbook 摘要，供 AI system 上下文注入。"""
    lines = ["## 我的交易体系 Playbook"]
    for section in load_playbook_sections():
        body = section.body_md.strip()
        preview = body.splitlines()[0][:100] if body else "（空）"
        lines.append(f"- **{section.title}**：{preview}")
    if status is not None:
        lines.extend(
            [
                "",
                "## 今日对照",
                f"- Profile：{status.profile_title} · {status.phase_label}",
                f"- 情绪：{status.emotion_label}（{status.emotion_position_hint}）",
                f"- 日盈亏：{status.daily_pnl_text}",
                f"- 计划：{status.plan_text}",
                f"- 持仓：{status.position_text}",
            ],
        )
        if status.discipline_progress:
            lines.append(f"- {status.discipline_progress}")
        if status.alert:
            lines.append(f"- 警示：{status.alert}")
    return "\n".join(lines)


def build_discipline_one_liner_prompt() -> str:
    return (
        "基于终端已注入的交易体系 Playbook 与今日对照状态，用**一句话**给出今日最重要的一条纪律提醒。\n"
        "要求：不超过 40 字；具体、可执行；若处于退潮/计划外持仓/纪律 checklist 未完成须点出；"
        "勿编造行情数据；可结合 get_emotion_cycle 补充环境判断。"
    )


def build_plan_review_prompt() -> str:
    return (
        "基于终端已注入的交易体系 Playbook 与今日对照（计划、持仓、情绪），"
        "检查今日操作是否偏离计划并给出应对建议；须结合 get_emotion_cycle，不要编造行情数据。"
    )


def build_position_discipline_prompt() -> str:
    return (
        "基于 Playbook 纪律规则与今日持仓对照，检查是否存在计划外持仓、"
        "退潮期违规开仓等纪律风险；可结合持仓记账核对，不要编造。"
    )


def build_playbook_page_quick_actions() -> list[QuickAction]:
    return [
        QuickAction(
            id="discipline_one_liner",
            label="今日一句纪律",
            auto_send=True,
            tooltip="结合 Playbook 与今日状态生成一句可执行纪律",
            prompt=build_discipline_one_liner_prompt(),
        ),
        QuickAction(
            id="plan_review",
            label="对照今日计划",
            auto_send=True,
            tooltip="对照 Playbook 计划、持仓与情绪阶段",
            prompt=build_plan_review_prompt(),
        ),
        QuickAction(
            id="position_discipline",
            label="持仓纪律检查",
            tooltip="检查计划外持仓与退潮期违规风险",
            prompt=build_position_discipline_prompt(),
        ),
    ]
