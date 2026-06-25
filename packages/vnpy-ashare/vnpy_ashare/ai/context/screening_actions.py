"""选股相关快捷动作（解读结果、Hub 雷达入口）。"""

from __future__ import annotations

from vnpy_ashare.ai.context.store import get_screening_results
from vnpy_common.ai.protocol import QuickAction


def build_interpret_screen_action() -> QuickAction | None:
    """最近一次选股/形态扫描结果解读（无结果时返回 None）。"""
    ctx = get_screening_results()
    if ctx is None or ctx.count <= 0:
        return None
    return QuickAction(
        id="interpret_screen",
        label="解读选股结果",
        auto_send=True,
        tooltip=f"解读「{ctx.condition}」共 {ctx.count} 条",
        prompt=(f"请解读选股结果「{ctx.condition}」（共 {ctx.count} 条）。分析板块分布、与上次变动差异及技术面特征后解读，不要编造。"),
    )


def build_screener_hub_quick_actions() -> list[QuickAction]:
    """选股 Hub 与雷达联动快捷入口（对齐左栏「雷达龙头 / 共振」）。"""
    return [
        QuickAction(
            id="screener_radar_leader",
            label="雷达龙头",
            auto_send=True,
            tooltip="须先在雷达页刷新；情绪 gate 通过后 run_leader_screen",
            prompt=("请先 get_emotion_cycle 与 get_radar_snapshot；若允许新开仓则 run_leader_screen 并解读龙头结果，不要编造。"),
        ),
        QuickAction(
            id="screener_radar_resonance",
            label="共振解读",
            auto_send=True,
            tooltip="解读雷达共振≥2 卡标的及龙头地位",
            prompt=("请调用 get_radar_snapshot，重点解读共振≥2 卡的标的及龙头地位，不要编造。"),
        ),
    ]
