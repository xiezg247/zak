"""板块资金页 AI 快捷动作。"""

from __future__ import annotations

from vnpy_common.ai.protocol import QuickAction


def build_sector_flow_structure_prompt() -> str:
    return (
        "请解读当前板块资金结构：哪些板块资金净流入/流出突出，与涨幅是否一致，短线需关注什么。"
        "结合终端已注入的板块快照；说明数据口径不确定性，不要编造未在摘要中的板块。"
    )


def build_sector_flow_rotation_prompt() -> str:
    return (
        "请解读近 15 日板块资金轮动：哪些板块持续净流入/流出，"
        "与当日快照是否形成共振或背离。结合终端已注入的轮动与延续摘要，不要编造。"
    )


def build_sector_flow_radar_leader_prompt() -> str:
    return (
        "请先 get_emotion_cycle 评估短线环境；若允许新开仓则 run_leader_screen 解读雷达龙头候选，"
        "并说明与当前板块资金主线的关系，不要编造未在工具结果中的标的。"
    )


def build_sector_flow_page_quick_actions() -> list[QuickAction]:
    return [
        QuickAction(
            id="sector_flow_structure",
            label="资金结构",
            tooltip="解读当日板块净流入/流出与涨幅一致性",
            prompt=build_sector_flow_structure_prompt(),
        ),
        QuickAction(
            id="sector_flow_rotation",
            label="板块轮动",
            tooltip="解读近 15 日资金轮动与当日共振/背离",
            prompt=build_sector_flow_rotation_prompt(),
        ),
        QuickAction(
            id="sector_flow_radar_leader",
            label="雷达龙头",
            tooltip="情绪 gate 通过后扫描龙头并与板块主线对照",
            prompt=build_sector_flow_radar_leader_prompt(),
        ),
    ]
