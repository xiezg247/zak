"""radar_leader_ready 触发与格式化测试。"""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import tests._bootstrap  # noqa: F401
from vnpy_ashare.domain.screener.result_row import ScreenerResultRow
from vnpy_ashare.domain.screener.run_result import build_screener_run_result
from vnpy_ashare.notifications.content.formatters import format_notify_text
from vnpy_ashare.notifications.core.events import NOTIFY_EVENT_RADAR_LEADER_READY
from vnpy_ashare.notifications.triggers.radar_leader_ready import build_radar_leader_ready_payload
from vnpy_ashare.services.screening import ScreeningService


def _leader_row(
    *,
    symbol: str = "600001",
    name: str = "测试龙头",
    leader_score: float = 72.0,
    leader_tier: str = "dragon_1",
    leader_tier_label: str = "龙一",
    sector_name: str = "人工智能",
) -> ScreenerResultRow:
    return ScreenerResultRow.from_mapping(
        {
            "symbol": symbol,
            "name": name,
            "leader_score": leader_score,
            "leader_tier": leader_tier,
            "leader_tier_label": leader_tier_label,
            "sector_name": sector_name,
        }
    )


class RadarLeaderReadyTriggerTest(unittest.TestCase):
    def _result(self, rows: list[ScreenerResultRow], *, condition: str = "雷达龙头 · 主线") -> object:
        return build_screener_run_result(
            rows=rows,
            condition=condition,
            updated_at="2026-06-18 10:15:00",
            total_scanned=120,
            source="radar_leader",
        )

    def test_build_payload_when_threshold_met(self) -> None:
        rows = [_leader_row(), _leader_row(symbol="600002", name="跟风A"), _leader_row(symbol="600003", name="跟风B")]
        payload = build_radar_leader_ready_payload(
            self._result(rows),
            {"leader_variant": "mainline"},
        )
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["hit_count"], 3)
        self.assertEqual(payload["top_symbol"], "600001")
        self.assertEqual(payload["top_score"], 72.0)
        self.assertEqual(payload["variant"], "mainline")

    def test_skip_when_hit_count_below_threshold(self) -> None:
        rows = [_leader_row(), _leader_row(symbol="600002", name="跟风A")]
        payload = build_radar_leader_ready_payload(self._result(rows), {})
        self.assertIsNone(payload)

    def test_skip_when_top_score_below_threshold(self) -> None:
        rows = [
            _leader_row(leader_score=50.0),
            _leader_row(symbol="600002", name="跟风A"),
            _leader_row(symbol="600003", name="跟风B"),
        ]
        payload = build_radar_leader_ready_payload(self._result(rows), {})
        self.assertIsNone(payload)

    def test_skip_when_condition_blocks_new_positions(self) -> None:
        rows = [_leader_row(), _leader_row(symbol="600002"), _leader_row(symbol="600003")]
        payload = build_radar_leader_ready_payload(
            self._result(rows, condition="退潮 · 不宜新开"),
            {},
        )
        self.assertIsNone(payload)

    def test_env_overrides_thresholds(self) -> None:
        rows = [_leader_row(leader_score=60.0), _leader_row(symbol="600002"), _leader_row(symbol="600003")]
        with patch.dict(os.environ, {"NOTIFY_RADAR_LEADER_MIN_HITS": "2", "NOTIFY_RADAR_LEADER_MIN_SCORE": "55"}):
            payload = build_radar_leader_ready_payload(self._result(rows), {})
        self.assertIsNotNone(payload)
        assert payload is not None
        self.assertEqual(payload["top_score"], 60.0)

    def test_format_notify_text_includes_leader(self) -> None:
        text = format_notify_text(
            NOTIFY_EVENT_RADAR_LEADER_READY,
            {
                "condition": "雷达龙头 · 主线",
                "hit_count": 4,
                "top_name": "测试龙头",
                "top_symbol": "600001",
                "top_score": 72,
                "top_tier_label": "龙一",
                "sector_name": "人工智能",
            },
        )
        self.assertIn("龙头池更新", text)
        self.assertIn("测试龙头", text)
        self.assertIn("龙一", text)
        self.assertIn("人工智能", text)


class ScreeningServiceRadarLeaderNotifyTest(unittest.TestCase):
    def test_persist_run_result_publishes_radar_leader_ready(self) -> None:
        engine = MagicMock()
        notify = MagicMock()
        engine.notification_service = notify
        service = ScreeningService(engine)
        rows = [_leader_row(), _leader_row(symbol="600002"), _leader_row(symbol="600003")]
        result = build_screener_run_result(
            rows=rows,
            condition="雷达龙头",
            updated_at="2026-06-18 10:15:00",
            total_scanned=80,
            source="radar_leader",
        )
        with (
            patch("vnpy_ashare.services.screening.save_run"),
            patch("vnpy_ashare.services.screening.publish_screener_page_context"),
            patch("vnpy_ashare.services.screening.enrich_condition_run", side_effect=lambda r, *_a, **_k: r),
        ):
            service.persist_run_result(result, trigger="radar_leader", extra_config={"leader_variant": "mainline"})
        notify.publish_radar_leader_ready.assert_called_once()
        call_result, call_config = notify.publish_radar_leader_ready.call_args[0]
        self.assertEqual(len(call_result.rows), 3)
        self.assertEqual(call_config.get("leader_variant"), "mainline")


if __name__ == "__main__":
    unittest.main()
