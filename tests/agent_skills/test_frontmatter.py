"""SKILL.md frontmatter 与 Agent 工具参数测试。"""

from __future__ import annotations

import json
import unittest

from pydantic import ValidationError

import tests._bootstrap  # noqa: F401
from vnpy_skills.agent.args import ReadSkillFileArgs, RunPythonArgs
from vnpy_skills.domain.frontmatter import SkillFrontmatter, parse_skill_document


class SkillFrontmatterTests(unittest.TestCase):
    def test_parse_yaml_credentials(self) -> None:
        text = """---
name: demo-skill
description: 测试技能
credentials:
  - name: DEMO_TOKEN
    description: demo token
requirements:
  environment_variables:
    - name: OPTIONAL_KEY
      required: false
---
# body
"""
        frontmatter, body = parse_skill_document(text)
        self.assertEqual(frontmatter.name, "demo-skill")
        self.assertEqual(len(frontmatter.credentials), 1)
        self.assertEqual(frontmatter.credentials[0].name, "DEMO_TOKEN")
        self.assertEqual(body, "# body")

        env = dict(frontmatter.env_requirements())
        self.assertEqual(env["DEMO_TOKEN"], True)
        self.assertEqual(env["OPTIONAL_KEY"], False)

    def test_parse_metadata_env(self) -> None:
        text = """---
name: tickflow
metadata: {"clawdbot":{"requires":{"env":["TICKFLOW_API_KEY"]}}}
---
"""
        frontmatter, _ = parse_skill_document(text)
        env = dict(frontmatter.env_requirements())
        self.assertIn("TICKFLOW_API_KEY", env)
        self.assertFalse(env["TICKFLOW_API_KEY"])

    def test_fallback_line_parser(self) -> None:
        text = """---
name: plain
description: "simple skill"
---
正文
"""
        frontmatter, body = parse_skill_document(text)
        self.assertEqual(frontmatter.name, "plain")
        self.assertEqual(frontmatter.description, "simple skill")
        self.assertEqual(body, "正文")

    def test_from_raw_keeps_extra_fields(self) -> None:
        fm = SkillFrontmatter.from_raw({"name": "x", "custom_flag": True})
        self.assertEqual(fm.name, "x")
        self.assertEqual(fm.model_extra, {"custom_flag": True})


class AgentToolArgsTests(unittest.TestCase):
    def test_read_skill_file_args_strip(self) -> None:
        args = ReadSkillFileArgs.model_validate({"skill": " tickflow ", "path": " SKILL.md "})
        self.assertEqual(args.skill, "tickflow")
        self.assertEqual(args.path, "SKILL.md")

    def test_read_skill_file_args_requires_path(self) -> None:
        with self.assertRaises(ValidationError):
            ReadSkillFileArgs.model_validate({"skill": "tickflow"})

    def test_run_python_args_allow_empty_code(self) -> None:
        args = RunPythonArgs.model_validate({"skill": "tickflow"})
        self.assertEqual(args.code, "")
        self.assertEqual(args.script_path, "")


class AgentToolValidationIntegrationTests(unittest.TestCase):
    def test_execute_tool_rejects_missing_path(self) -> None:
        from vnpy_skills.app.engine import SkillEngine

        engine = SkillEngine()
        result = engine.execute_tool("read_skill_file", {"skill": "missing"})
        payload = json.loads(result)
        self.assertEqual(payload["error"], "参数错误")
        self.assertIn("details", payload)


if __name__ == "__main__":
    unittest.main()
