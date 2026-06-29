"""vnpy-notes Skill 测试。"""

from __future__ import annotations

import json
import unittest
from unittest.mock import Mock

from vnpy.trader.constant import Exchange

import tests._bootstrap  # noqa: F401
from skills.vnpy_notes_skill import VnpyNotesSkill
from tests.ashare.pg_unittest import PgStorageTestCase
from vnpy_ashare.services.note import NoteService


class VnpyNotesSkillTests(PgStorageTestCase):
    def setUp(self) -> None:
        super().setUp()
        engine = Mock()
        engine.main_engine = None
        engine.event_engine = None
        self.note_service = NoteService(engine)
        self.skill = VnpyNotesSkill()
        self.skill._services = {"note": self.note_service}

    def test_get_and_append_notes(self) -> None:
        raw = self.skill.get_stock_notes("600519.SSE")
        payload = json.loads(raw)
        self.assertEqual(payload["memo"], None)
        self.assertEqual(payload["entries"], [])

        append_raw = self.skill.append_stock_note_entry("600519.SSE", "突破均线")
        append_payload = json.loads(append_raw)
        self.assertTrue(append_payload["success"])

        self.skill.update_stock_note_memo("600519.SSE", "长期逻辑")
        raw = self.skill.get_stock_notes("600519.SSE")
        payload = json.loads(raw)
        self.assertEqual(payload["memo"]["body"], "长期逻辑")
        self.assertEqual(len(payload["entries"]), 1)

    def test_delete_and_clear(self) -> None:
        append_raw = self.skill.append_stock_note_entry("600000.SSE", "观察")
        entry_id = json.loads(append_raw)["entry"]["id"]
        delete_raw = self.skill.delete_stock_note_entry(entry_id)
        self.assertTrue(json.loads(delete_raw)["success"])

        self.skill.update_stock_note_memo("600000.SSE", "备忘")
        clear_raw = self.skill.clear_stock_notes("600000.SSE")
        cleared = json.loads(clear_raw)["cleared"]
        self.assertGreaterEqual(cleared["memos"], 1)

    def test_list_and_get_reports(self) -> None:
        self.note_service.create_report(
            "600519",
            Exchange.SSE,
            title="AI 解读",
            body="## 结论\n看好",
            source_scope="overview",
        )
        list_raw = self.skill.list_stock_analysis_reports("600519.SSE")
        listed = json.loads(list_raw)
        self.assertEqual(listed["count"], 1)
        report_id = listed["reports"][0]["id"]
        get_raw = self.skill.get_stock_analysis_report(report_id)
        payload = json.loads(get_raw)
        self.assertIn("看好", payload["body"])


if __name__ == "__main__":
    unittest.main()
