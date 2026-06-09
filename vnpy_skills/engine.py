"""技能加载与管理。

- Agent Skill：skills/<name>/SKILL.md（官方 tushare-data、tickflow 等）
- Python Skill：skills/*.py 继承 SkillTemplate（自编写扩展）
"""

from __future__ import annotations

import importlib
import traceback
from glob import glob
from pathlib import Path
from types import ModuleType
from typing import Any

from dotenv import load_dotenv

from vnpy_ashare.paths import ENV_FILE, PROJECT_ROOT
from vnpy_skills.agent_skill import AgentSkill
from vnpy_skills.base import SkillTemplate, ToolSpec
from vnpy_skills.builtin_tools import AGENT_TOOL_SPECS
from vnpy_skills.runner import read_skill_file, run_python_in_skill

APP_NAME = "Skills"
DEFAULT_SKILLS_DIR = PROJECT_ROOT / "skills"


class SkillEngine:
    """加载 Agent Skills + 自编写 Python Skills，聚合 LLM 工具。"""

    def __init__(
        self,
        skills_dir: Path | None = None,
        services: dict[str, object] | None = None,
    ) -> None:
        self.skills_dir = (skills_dir or DEFAULT_SKILLS_DIR).resolve()
        self._services = services or {}
        self.agent_skills: dict[str, AgentSkill] = {}
        self.classes: dict[str, type[SkillTemplate]] = {}
        self.instances: dict[str, SkillTemplate] = {}
        self._tool_index: dict[str, str] = {}
        self._agent_tool_owner = "__agent__"

    def load_all(self) -> None:
        load_dotenv(ENV_FILE, override=False)
        self.load_agent_skills()
        self.load_python_skills()

    def load_agent_skills(self) -> None:
        self.agent_skills.clear()
        if not self.skills_dir.is_dir():
            return

        for entry in sorted(self.skills_dir.iterdir()):
            if not entry.is_dir() or entry.name.startswith(("_", ".")):
                continue
            skill = AgentSkill.from_directory(entry)
            if skill is not None:
                self.agent_skills[skill.name] = skill

    def load_python_skills(self) -> None:
        self.classes.clear()
        if not self.skills_dir.is_dir():
            return
        self.load_python_skills_from_folder(self.skills_dir, "skills")

    def load_python_skills_from_folder(self, path: Path, module_name: str) -> None:
        for suffix in ("py",):
            pathname = str(path.joinpath(f"*.{suffix}"))
            for filepath in glob(pathname):
                filename = Path(filepath).stem
                if filename.startswith("_") or filename == "registry":
                    continue
                name = f"{module_name}.{filename}"
                self.load_python_skill_from_module(name)

    def load_python_skill_from_module(self, module_name: str) -> None:
        try:
            module: ModuleType = importlib.import_module(module_name)
            importlib.reload(module)

            for attr_name in dir(module):
                value = getattr(module, attr_name)
                if isinstance(value, type) and issubclass(value, SkillTemplate) and value is not SkillTemplate:
                    self.classes[value.__name__] = value
        except Exception:
            print(f"Python Skill 模块 {module_name} 加载失败:\n{traceback.format_exc()}")

    def init_skills(self) -> list[str]:
        """初始化并返回已启用 skill 名称列表。"""
        self.instances.clear()
        self._tool_index.clear()
        enabled: list[str] = []

        for name, skill in sorted(self.agent_skills.items()):
            if skill.available:
                enabled.append(name)

        for class_name, cls in sorted(self.classes.items()):
            instance = cls()
            instance._services = self._services
            instance.on_init()
            if not instance.available:
                continue
            instance.setup()
            key = instance.skill_name or class_name
            self.instances[key] = instance
            enabled.append(key)
            for spec in instance.get_tools():
                self._tool_index[spec.name] = key

        for spec in AGENT_TOOL_SPECS:
            self._tool_index[spec.name] = self._agent_tool_owner

        return enabled

    def reload_skills(self) -> list[str]:
        self.load_all()
        return self.init_skills()

    def get_enabled_agent_skills(self) -> list[AgentSkill]:
        return [s for s in self.agent_skills.values() if s.available]

    def build_skills_prompt(self) -> str:
        """将已加载 Agent Skill 的 SKILL.md 正文注入系统提示。"""
        skills = self.get_enabled_agent_skills()
        if not skills and not self.instances:
            return ""

        parts = [
            "【已加载 Skills】",
            "以下 skill 包来自官方 SKILL.md；系统提示仅含名称与简介，",
            "详细说明请通过 read_skill_file / run_python / list_skill_files 按需查阅。",
            "涉及行情、财务、宏观数据时必须先调用工具取数，禁止编造。",
            "",
        ]
        for skill in skills:
            parts.append(skill.prompt_section())
            refs = skill.list_files("references")
            if refs:
                parts.append(f"可用参考文档：{', '.join(refs[:8])}")
                if len(refs) > 8:
                    parts.append(f"... 共 {len(refs)} 个文件，可用 list_skill_files 查看")
            scripts = skill.list_files("scripts")
            if scripts:
                parts.append(f"可用脚本：{', '.join(scripts)}")
            parts.append("")

        if self.instances:
            parts.append("【自编写 Python Skills】")
            for key, inst in sorted(self.instances.items()):
                parts.append(f"- {key}: {inst.description or inst.__class__.__name__}")

        return "\n".join(parts).strip()

    def get_openai_tools(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = []
        if self.get_enabled_agent_skills():
            for spec in AGENT_TOOL_SPECS:
                tools.append(spec.to_openai_tool())
        for skill in self.instances.values():
            for spec in skill.get_tools():
                tools.append(spec.to_openai_tool())
        return tools

    def get_tool_specs(self) -> list[ToolSpec]:
        specs: list[ToolSpec] = []
        if self.get_enabled_agent_skills():
            specs.extend(AGENT_TOOL_SPECS)
        for skill in self.instances.values():
            specs.extend(skill.get_tools())
        return specs

    def execute_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if name in {spec.name for spec in AGENT_TOOL_SPECS}:
            return self._execute_agent_tool(name, arguments)

        owner = self._tool_index.get(name)
        if owner is None:
            return f'{{"error": "未注册的工具: {name}"}}'
        if owner == self._agent_tool_owner:
            return self._execute_agent_tool(name, arguments)
        return self.instances[owner].call_tool(name, arguments)

    def _execute_agent_tool(self, name: str, arguments: dict[str, Any]) -> str:
        skill_name = str(arguments.get("skill", "")).strip()
        skill = self.agent_skills.get(skill_name)
        if skill is None:
            return f'{{"error": "未知 skill: {skill_name}，已加载: {list(self.agent_skills.keys())}"}}'

        if name == "read_skill_file":
            path = str(arguments.get("path", "")).strip()
            return read_skill_file(skill, path)

        if name == "list_skill_files":
            subdir = str(arguments.get("subdir", "")).strip()
            files = skill.list_files(subdir)
            return "\n".join(files) if files else "(无文件)"

        if name == "run_python":
            code = str(arguments.get("code", ""))
            script_path = str(arguments.get("script_path", ""))
            return run_python_in_skill(skill, code, script_path=script_path)

        return f'{{"error": "未知 Agent 工具: {name}"}}'

    def skill_names(self) -> list[str]:
        names = [s.name for s in self.get_enabled_agent_skills()]
        names.extend(self.instances.keys())
        return names

    # 兼容旧 API
    def load_skill_class(self) -> None:
        self.load_all()
