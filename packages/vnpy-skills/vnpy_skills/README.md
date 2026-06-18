# vnpy_skills

VeighNa **AI 工具技能框架**：加载 Agent Skill（`SKILL.md`）与自编写 Python Skill，聚合 LLM 工具。

## 使用

```python
from vnpy_skills.app.engine import SkillEngine

engine = SkillEngine(services={...})
engine.load_all()
engine.init_skills()
```

## 包结构

```
vnpy_skills/
├── app/           # SkillEngine
├── domain/        # SkillTemplate、ToolSpec
└── agent/         # AgentSkill、runner、通用 Agent 工具
```

## 核心入口

| 路径 | 说明 |
|------|------|
| `app/engine.py` | SkillEngine（加载、初始化、工具执行） |
| `domain/template.py` | `SkillTemplate`、`ToolSpec` 基类 |
| `agent/skill.py` | `AgentSkill`（SKILL.md 解析） |
| `agent/runner.py` | `read_skill_file`、`run_python_in_skill` |
| `agent/tools.py` | Agent 通用工具（read/list/run） |

技能目录默认 `skills/`（Agent Skill 子目录 + `*.py` Python Skill）。

依赖 `vnpy-common`（路径）。

## 扩展 Python Skill

```python
from vnpy_skills.domain.template import SkillTemplate, ToolSpec

class MySkill(SkillTemplate):
    skill_name = "my_skill"
    ...
```
