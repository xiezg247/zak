"""vnpy_skills 与官方 Agent Skills 测试。"""

from __future__ import annotations

import unittest
from unittest.mock import patch

import tests._bootstrap  # noqa: F401
from tests._bootstrap import PROJECT_ROOT

from skills.registry import OFFICIAL_SKILLS, format_skills_prompt
from vnpy_skills.agent_skill import AgentSkill
from vnpy_skills.engine import SkillEngine


class AgentSkillTests(unittest.TestCase):
    def test_parse_tushare_data_if_synced(self) -> None:
        root = PROJECT_ROOT / "skills" / "tushare-data"
        if not (root / "SKILL.md").is_file():
            self.skipTest("请先运行 scripts/sync_skills.py")
        skill = AgentSkill.from_directory(root)
        assert skill is not None
        self.assertEqual(skill.name, "tushare-data")
        self.assertIn("Tushare", skill.description)

    def test_parse_tickflow_if_synced(self) -> None:
        root = PROJECT_ROOT / "skills" / "tickflow"
        if not (root / "SKILL.md").is_file():
            self.skipTest("请先运行 scripts/sync_skills.py")
        skill = AgentSkill.from_directory(root)
        assert skill is not None
        self.assertEqual(skill.name, "tickflow")

    def test_read_reference_if_synced(self) -> None:
        root = PROJECT_ROOT / "skills" / "tushare-data"
        ref = root / "references" / "数据接口.md"
        if not ref.is_file():
            self.skipTest("请先运行 scripts/sync_skills.py")
        skill = AgentSkill.from_directory(root)
        assert skill is not None
        text = skill.read_file("references/数据接口.md", max_chars=500)
        self.assertIn("接口", text)

    def test_path_traversal_blocked(self) -> None:
        root = PROJECT_ROOT / "skills" / "tickflow"
        if not (root / "SKILL.md").is_file():
            self.skipTest("请先运行 scripts/sync_skills.py")
        skill = AgentSkill.from_directory(root)
        assert skill is not None
        self.assertIsNone(skill.resolve_path("../secret.txt"))


class SkillEngineTests(unittest.TestCase):
    def test_load_official_skills(self) -> None:
        if not (PROJECT_ROOT / "skills" / "tushare-data" / "SKILL.md").is_file():
            self.skipTest("请先运行 scripts/sync_skills.py")
        engine = SkillEngine()
        engine.load_all()
        enabled = engine.init_skills()
        self.assertIn("tushare-data", enabled)
        self.assertIn("tickflow", enabled)
        tools = {spec.name for spec in engine.get_tool_specs()}
        self.assertIn("read_skill_file", tools)
        self.assertIn("run_python", tools)

    def test_build_skills_prompt(self) -> None:
        if not (PROJECT_ROOT / "skills" / "tickflow" / "SKILL.md").is_file():
            self.skipTest("请先运行 scripts/sync_skills.py")
        engine = SkillEngine()
        engine.load_all()
        engine.init_skills()
        prompt = engine.build_skills_prompt()
        self.assertIn("tickflow", prompt)
        self.assertIn("read_skill_file", prompt)
        skill = engine.agent_skills["tickflow"]
        if skill.body.strip():
            marker = skill.body.strip().splitlines()[0][:40]
            if len(marker) > 10 and marker not in skill.description:
                self.assertNotIn(marker, prompt)

    def test_prompt_section_is_summary_only(self) -> None:
        if not (PROJECT_ROOT / "skills" / "tickflow" / "SKILL.md").is_file():
            self.skipTest("请先运行 scripts/sync_skills.py")
        skill = AgentSkill.from_directory(PROJECT_ROOT / "skills" / "tickflow")
        assert skill is not None
        summary = skill.prompt_section()
        self.assertIn("read_skill_file", summary)
        if skill.body.strip():
            marker = skill.body.strip().splitlines()[0][:40]
            if len(marker) > 10 and marker not in skill.description:
                self.assertNotIn(marker, summary)

    def test_execute_read_skill_file(self) -> None:
        if not (PROJECT_ROOT / "skills" / "tickflow" / "SKILL.md").is_file():
            self.skipTest("请先运行 scripts/sync_skills.py")
        engine = SkillEngine()
        engine.load_all()
        engine.init_skills()
        result = engine.execute_tool(
            "read_skill_file",
            {"skill": "tickflow", "path": "SKILL.md"},
        )
        self.assertIn("TickFlow", result)

    @patch("vnpy_skills.runner.subprocess.run")
    def test_execute_run_python(self, mock_run) -> None:
        if not (PROJECT_ROOT / "skills" / "tickflow" / "SKILL.md").is_file():
            self.skipTest("请先运行 scripts/sync_skills.py")
        mock_run.return_value = type(
            "R",
            (),
            {"stdout": "ok", "stderr": "", "returncode": 0},
        )()
        engine = SkillEngine()
        engine.load_all()
        engine.init_skills()
        result = engine.execute_tool(
            "run_python",
            {"skill": "tickflow", "code": "print('hi')"},
        )
        self.assertIn("ok", result)


class RegistryTests(unittest.TestCase):
    def test_official_meta(self) -> None:
        self.assertIn("tushare-data", OFFICIAL_SKILLS)
        self.assertIn("tickflow", OFFICIAL_SKILLS)

    def test_format_prompt(self) -> None:
        text = format_skills_prompt(["tushare-data", "tickflow"])
        self.assertIn("Tushare", text)


if __name__ == "__main__":
    unittest.main()
