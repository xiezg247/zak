"""Repository 层 user_id SQL 片段。"""

from __future__ import annotations


def user_sql(extra: str = "") -> str:
    """生成 `user_id = ?` 过滤片段。"""
    if extra:
        return f"user_id = ? AND {extra}"
    return "user_id = ?"
