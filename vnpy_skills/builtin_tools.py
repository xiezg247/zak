"""Agent Skill 通用工具定义。"""

from __future__ import annotations

from vnpy_skills.base import ToolSpec

READ_SKILL_FILE = ToolSpec(
    name="read_skill_file",
    description=(
        "读取 skill 包内文件（如 references/数据接口.md、scripts/*.py、SKILL.md）。"
        "查 Tushare 接口文档或 TickFlow 示例时优先使用。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "skill": {
                "type": "string",
                "description": "skill 名称，如 tushare-data、tickflow",
            },
            "path": {
                "type": "string",
                "description": "相对 skill 根目录的路径，如 references/数据接口.md",
            },
        },
        "required": ["skill", "path"],
    },
)

RUN_PYTHON = ToolSpec(
    name="run_python",
    description=(
        "在指定 skill 目录下执行 Python 代码或脚本。"
        "用于调用 tushare / tickflow 等数据接口。"
        "code 与 script_path 二选一；script_path 如 scripts/stock_data_demo.py。"
    ),
    parameters={
        "type": "object",
        "properties": {
            "skill": {
                "type": "string",
                "description": "skill 名称，如 tushare-data、tickflow",
            },
            "code": {
                "type": "string",
                "description": "要执行的 Python 源码",
            },
            "script_path": {
                "type": "string",
                "description": "skill 内脚本相对路径（可选）",
            },
        },
        "required": ["skill"],
    },
)

LIST_SKILL_FILES = ToolSpec(
    name="list_skill_files",
    description="列出 skill 包内可用文件（references、scripts 等）",
    parameters={
        "type": "object",
        "properties": {
            "skill": {
                "type": "string",
                "description": "skill 名称",
            },
            "subdir": {
                "type": "string",
                "description": "子目录，如 references 或 scripts，留空表示全部",
            },
        },
        "required": ["skill"],
    },
)

AGENT_TOOL_SPECS = [READ_SKILL_FILE, RUN_PYTHON, LIST_SKILL_FILES]
