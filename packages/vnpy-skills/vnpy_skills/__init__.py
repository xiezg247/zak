"""vnpy_skills：AI 工具技能框架。"""

from vnpy_skills.agent import AgentSkill
from vnpy_skills.app.engine import APP_NAME, SkillEngine
from vnpy_skills.domain import SkillTemplate, ToolSpec

__all__ = ["APP_NAME", "AgentSkill", "SkillEngine", "SkillTemplate", "ToolSpec"]
