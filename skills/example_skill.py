"""自编写 Python Skill 示例（可选）。

继承 SkillTemplate 并放在 skills/*.py，vnpy_skills 会自动加载。
官方 tushare-data / tickflow 请用 scripts/sync_skills.py 同步，无需手写。
"""

from __future__ import annotations

import json

from vnpy_skills.base import SkillTemplate, ToolSpec


class ExampleSkill(SkillTemplate):
    """示例：演示如何扩展自定义工具（默认不启用）。"""

    skill_name = "example"
    author = "vnpy_zak"
    description = "示例自编写 Skill"

    @property
    def available(self) -> bool:
        # 设为 False 避免加载示例；自编写时改为 True
        return False

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="echo_message",
                description="回显消息（示例）",
                parameters={
                    "type": "object",
                    "properties": {
                        "message": {"type": "string", "description": "要回显的文本"},
                    },
                    "required": ["message"],
                },
            ),
        ]

    def echo_message(self, message: str) -> str:
        return json.dumps({"echo": message}, ensure_ascii=False)
