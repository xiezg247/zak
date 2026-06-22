"""vnpy-radar Skill 测试。"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from skills.vnpy_radar_skill import VnpyRadarSkill


def _make_skill(*, screening: MagicMock | None = None, radar: MagicMock | None = None) -> VnpyRadarSkill:
    skill = VnpyRadarSkill()
    skill._services = {
        "screening": screening or MagicMock(),
        "radar": radar or MagicMock(),
    }
    return skill


def test_get_radar_snapshot_empty() -> None:
    radar = MagicMock()
    radar.snapshot_to_dict.return_value = {"status": "empty"}
    skill = _make_skill(radar=radar)
    payload = json.loads(skill.get_radar_snapshot())
    assert payload["status"] == "empty"


def test_run_short_term_screen_persists() -> None:
    screening = MagicMock()
    skill = _make_skill(screening=screening)
    with patch(
        "skills.vnpy_radar_skill.run_short_term_screen",
        return_value=MagicMock(
            rows=[{"vt_symbol": "600000.SSE", "symbol": "600000", "name": "浦发银行"}],
            condition="极致短线",
            source="short_term",
            updated_at="t",
            total_scanned=100,
        ),
    ):
        raw = skill.run_short_term_screen(top_n=5)
    payload = json.loads(raw)
    assert payload["status"] == "ok"
    assert payload["count"] == 1
    screening.persist_run_result.assert_called_once()
