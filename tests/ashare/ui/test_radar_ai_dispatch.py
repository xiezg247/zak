"""雷达 AI 请求编排。"""

from __future__ import annotations

from unittest.mock import patch

from vnpy_ashare.quotes.radar.loaders import RadarCardData, RadarRow
from vnpy_ashare.ui.quotes.radar.ai_dispatch import (
    RadarAiReject,
    RadarAiRequest,
    plan_eod_leader_ai,
    plan_radar_board_ai,
    plan_radar_card_ai,
    plan_resonance_ai,
)


def _card(card_id: str, title: str = "卡", *rows: RadarRow) -> RadarCardData:
    return RadarCardData(
        card_id=card_id,
        title=title,
        subtitle="",
        rows=rows,
        empty_message="" if rows else "空",
        updated_at="",
    )


def test_plan_board_ai_empty() -> None:
    assert isinstance(plan_radar_board_ai({}), RadarAiReject)


def test_plan_board_ai_ok() -> None:
    with patch(
        "vnpy_ashare.ui.quotes.radar.ai_dispatch.build_radar_ai_prompt",
        return_value="prompt",
    ):
        out = plan_radar_board_ai({"a": _card("a")})
    assert isinstance(out, RadarAiRequest)
    assert out.prompt == "prompt"
    assert out.source_page == "雷达"


def test_plan_card_ai() -> None:
    payload = {"a": _card("a", "龙头")}
    assert isinstance(plan_radar_card_ai(payload, "missing"), RadarAiReject)
    with (
        patch("vnpy_ashare.ui.quotes.radar.ai_dispatch.compute_radar_resonance", return_value={}),
        patch(
            "vnpy_ashare.ui.quotes.radar.ai_dispatch.build_radar_card_ai_prompt",
            return_value="",
        ),
    ):
        assert isinstance(plan_radar_card_ai(payload, "a"), RadarAiReject)
    with (
        patch("vnpy_ashare.ui.quotes.radar.ai_dispatch.compute_radar_resonance", return_value={}),
        patch(
            "vnpy_ashare.ui.quotes.radar.ai_dispatch.build_radar_card_ai_prompt",
            return_value="card-prompt",
        ),
    ):
        out = plan_radar_card_ai(payload, "a")
    assert isinstance(out, RadarAiRequest)
    assert out.source_page == "雷达·龙头"


def test_plan_eod_and_resonance() -> None:
    assert isinstance(plan_eod_leader_ai({}), RadarAiReject)
    assert isinstance(plan_resonance_ai({}), RadarAiReject)
    with patch(
        "vnpy_ashare.ui.quotes.radar.ai_dispatch.build_eod_leader_prompt",
        return_value="",
    ):
        assert isinstance(plan_eod_leader_ai({"a": _card("a")}), RadarAiReject)
    with patch(
        "vnpy_ashare.ui.quotes.radar.ai_dispatch.build_radar_resonance_ai_prompt",
        return_value="res",
    ):
        out = plan_resonance_ai({"a": _card("a")})
    assert isinstance(out, RadarAiRequest)
    assert "共振" in out.status_text
