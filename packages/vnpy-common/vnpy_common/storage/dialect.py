"""SQL 方言辅助。"""

from __future__ import annotations


def split_sql_script(script: str) -> list[str]:
    """按分号拆分 executescript 语句（忽略空段）。"""
    parts: list[str] = []
    for chunk in script.split(";"):
        statement = chunk.strip()
        if statement:
            parts.append(statement)
    return parts
