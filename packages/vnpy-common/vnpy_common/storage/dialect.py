"""SQL 方言辅助：占位符与 DDL 适配。"""

from __future__ import annotations


def to_positional_sql(sql: str) -> str:
    """将 SQLite 风格 `?` 占位符转为 PostgreSQL `%s`。

    包括 `?::jsonb`、`?::text` 等写法——`?` 在应用层 SQL 中始终是占位符。
    """
    return sql.replace("?", "%s")


def split_sql_script(script: str) -> list[str]:
    """按分号拆分 executescript 语句（忽略空段）。"""
    parts: list[str] = []
    for chunk in script.split(";"):
        statement = chunk.strip()
        if statement:
            parts.append(statement)
    return parts
