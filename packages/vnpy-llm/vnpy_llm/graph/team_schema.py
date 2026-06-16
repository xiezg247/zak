"""投研团队：子 Agent 结构化评分 schema 与解析。"""

from __future__ import annotations

import json
import re
from typing import Any

TEAM_SCORE_JSON_EXAMPLE = """```json
{
  "score": 75,
  "summary": "一句话总结",
  "highlights": ["亮点1"],
  "risks": ["风险1"],
  "raw_data": {}
}
```"""

TEAM_SCORE_JSON_INSTRUCTION = (
    "在 Markdown 分析末尾用 ```json 代码块输出结构化评分，字段必须为："
    "score（0-100 整数）、summary、highlights、risks、raw_data。"
    "禁止嵌套 financial/risk/strategy 外层键。"
)


def normalize_agent_score(data: dict[str, Any] | None, dimension: str) -> dict[str, Any] | None:
    """兼容扁平 score 与历史嵌套 {financial: {score}} 格式。"""
    if not data:
        return None
    nested = data.get(dimension)
    if isinstance(nested, dict) and nested.get("score") is not None:
        return nested
    if data.get("score") is not None:
        return data
    return None


def extract_agent_score(text: str, dimension: str) -> dict[str, Any] | None:
    pattern = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
    matches = pattern.findall(text)
    if not matches:
        return None
    try:
        parsed = json.loads(matches[-1])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return normalize_agent_score(parsed, dimension)
