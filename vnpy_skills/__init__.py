"""vnpy_skills：AI 工具技能框架。"""

from vnpy_skills.agent_skill import AgentSkill
from vnpy_skills.base import SkillTemplate, ToolSpec
from vnpy_skills.engine import APP_NAME, SkillEngine

__all__ = ["APP_NAME", "AgentSkill", "SkillEngine", "SkillTemplate", "ToolSpec"]
