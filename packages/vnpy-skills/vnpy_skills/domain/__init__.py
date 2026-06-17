"""Skill 领域模型。"""

from vnpy_common.domain.base import FrozenModel, MutableModel
from vnpy_skills.domain.frontmatter import SkillFrontmatter
from vnpy_skills.domain.template import SkillTemplate, ToolSpec

__all__ = ["FrozenModel", "MutableModel", "SkillFrontmatter", "SkillTemplate", "ToolSpec"]
