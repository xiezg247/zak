"""雷达 AI 请求编排（纯函数：校验 payload → prompt / 拒绝原因）。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from vnpy_ashare.quotes.radar.loaders import (
    RadarCardData,
    build_eod_leader_prompt,
    build_radar_ai_prompt,
    build_radar_card_ai_prompt,
    build_radar_resonance_ai_prompt,
    compute_radar_resonance,
)


@dataclass(frozen=True, slots=True)
class RadarAiRequest:
    prompt: str
    source_page: str
    status_text: str


@dataclass(frozen=True, slots=True)
class RadarAiReject:
    message: str
    level: str = "warning"


RadarAiOutcome = RadarAiRequest | RadarAiReject


def _reject_empty_payload() -> RadarAiReject:
    return RadarAiReject("请先刷新雷达数据")


def plan_radar_board_ai(payload: Mapping[str, RadarCardData]) -> RadarAiOutcome:
    if not payload:
        return _reject_empty_payload()
    prompt = build_radar_ai_prompt(dict(payload))
    return RadarAiRequest(
        prompt=prompt,
        source_page="雷达",
        status_text="已发送 AI 洞察请求",
    )


def plan_radar_card_ai(
    payload: Mapping[str, RadarCardData],
    card_id: str,
) -> RadarAiOutcome:
    data = payload.get(card_id)
    if data is None:
        return RadarAiReject("请先刷新该卡片")
    resonance = compute_radar_resonance(dict(payload))
    prompt = build_radar_card_ai_prompt(
        card_id,
        data,
        resonance_counts=resonance,
    )
    if not prompt:
        return RadarAiReject("该卡片暂无可解读内容")
    return RadarAiRequest(
        prompt=prompt,
        source_page=f"雷达·{data.title}",
        status_text=f"已发送「{data.title}」AI 解读",
    )


def plan_eod_leader_ai(payload: Mapping[str, RadarCardData]) -> RadarAiOutcome:
    if not payload:
        return _reject_empty_payload()
    prompt = build_eod_leader_prompt(dict(payload))
    if not prompt:
        return RadarAiReject("缺少龙头/梯队卡片数据，请先刷新相关卡片")
    return RadarAiRequest(
        prompt=prompt,
        source_page="雷达",
        status_text="已发送盘后龙头解读请求",
    )


def plan_resonance_ai(payload: Mapping[str, RadarCardData]) -> RadarAiOutcome:
    if not payload:
        return _reject_empty_payload()
    prompt = build_radar_resonance_ai_prompt(dict(payload))
    if not prompt:
        return RadarAiReject("当前无共振标的")
    return RadarAiRequest(
        prompt=prompt,
        source_page="雷达",
        status_text="已发送共振 AI 解读请求",
    )
