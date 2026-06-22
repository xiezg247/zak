"""雷达页 AI 上下文。"""

from __future__ import annotations

from vnpy_ashare.domain.radar.snapshot import RadarBoardSnapshot
from vnpy_ashare.quotes.radar.radar_board_store import get_radar_board_snapshot
from vnpy_common.ai.protocol import QuickAction


def format_radar_page_extra(snapshot: RadarBoardSnapshot | None = None) -> str:
    """格式化雷达页 extra 文本（与 build_radar_ai_prompt 头部对齐）。"""
    data = snapshot if snapshot is not None else get_radar_board_snapshot()
    if data is None:
        return "【雷达快照】暂无数据，请先刷新雷达页。"

    lines = ["【雷达快照】"]
    if data.emotion_stage_label:
        gate = "可做" if data.allow_new_positions else "不宜新开"
        lines.append(f"情绪：{data.emotion_stage_label}（{gate}）")
    lines.append(f"共振 {data.resonance_count} 只 · 龙一 {data.dragon_1_count} 只")
    if data.board_updated_at:
        lines.append(f"更新：{data.board_updated_at}")

    if data.resonance_entries:
        parts: list[str] = []
        for entry in data.resonance_entries[:5]:
            tier = f"·{entry.leader_tier}" if entry.leader_tier else ""
            parts.append(f"{entry.name}({entry.card_count}卡{tier})")
        lines.append("共振 Top：" + "、".join(parts))

    return "\n".join(lines)


def build_radar_page_quick_actions() -> list[QuickAction]:
    """雷达页无选中个股时的快捷动作。"""
    return [
        QuickAction(
            id="radar_insight",
            label="今日洞察",
            auto_send=True,
            prompt="请调用 get_radar_snapshot 解读当前雷达盘面：主线、共振与龙头结构，不要编造未出现的标的。",
        ),
        QuickAction(
            id="radar_resonance",
            label="共振解读",
            auto_send=True,
            prompt="请调用 get_radar_snapshot，重点解读共振≥2卡的标的及龙头地位，不要编造。",
        ),
        QuickAction(
            id="radar_short_term",
            label="抓短线龙头",
            auto_send=True,
            prompt="请先 get_radar_snapshot 看环境；若允许新开仓则 run_short_term_screen 并解读结果，不要编造。",
        ),
        QuickAction(
            id="radar_eod",
            label="盘后龙头复盘",
            prompt="请基于 get_radar_snapshot 完成今日龙头结构 + 明日观察复盘，不要编造具体买卖价。",
        ),
    ]
