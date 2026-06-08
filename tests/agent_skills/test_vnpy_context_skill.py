"""vnpy_context_skill 测试。"""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

import tests._bootstrap  # noqa: F401

from vnpy_ashare.ai.context import AiContextData
from vnpy_skills.engine import SkillEngine

from skills.vnpy_context_skill import VnpyContextSkill


class VnpyContextSkillTests(unittest.TestCase):
    def setUp(self) -> None:
        self.skill = VnpyContextSkill()
        self.skill.setup()

    def _inject_quote_service(self, ctx: AiContextData) -> None:
        mock_svc = MagicMock()
        mock_svc.get_current_context.return_value = ctx
        self.skill._services = {"quote": mock_svc}

    def test_get_quote_context_empty(self) -> None:
        self._inject_quote_service(AiContextData())
        payload = json.loads(self.skill.get_quote_context())
        self.assertIn("message", payload)

    def test_get_quote_context_with_data(self) -> None:
        self._inject_quote_service(
            AiContextData(
                page="自选",
                symbol="600519",
                exchange="SSE",
                name="贵州茅台",
                quote_summary="最新价 1500.00",
                extra="本地日 K 条数：120",
            )
        )
        payload = json.loads(self.skill.get_quote_context())
        self.assertEqual(payload["name"], "贵州茅台")
        self.assertIn("1500", payload["quote_summary"])

    def test_get_quote_context_no_service(self) -> None:
        self.skill._services = {}
        payload = json.loads(self.skill.get_quote_context())
        self.assertIn("未就绪", payload["message"])


class SkillEngineIntegrationTests(unittest.TestCase):
    def test_load_vnpy_context_skill(self) -> None:
        engine = SkillEngine()
        engine.load_all()
        enabled = engine.init_skills()
        self.assertIn("vnpy-context", enabled)
        tool_names = {spec.name for spec in engine.get_tool_specs()}
        self.assertIn("get_quote_context", tool_names)

    def test_load_unmodified_skill_returns_one_tool(self) -> None:
        engine = SkillEngine()
        engine.load_all()
        engine.init_skills()
        skill = engine.instances.get("vnpy-context")
        self.assertIsNotNone(skill)
        tools = skill.get_tools()
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0].name, "get_quote_context")


if __name__ == "__main__":
    unittest.main()
