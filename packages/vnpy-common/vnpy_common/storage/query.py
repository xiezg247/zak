"""SQLAlchemy Core 查询辅助。"""

from __future__ import annotations

from sqlalchemy import and_
from sqlalchemy.sql.elements import ColumnElement


def user_scope(user_id_col, uid: str, *extras: ColumnElement[bool]) -> ColumnElement[bool]:
    """替代 user_sql()：生成 user_id = uid [AND ...] 条件。"""
    clauses: list[ColumnElement[bool]] = [user_id_col == uid, *extras]
    if len(clauses) == 1:
        return clauses[0]
    return and_(*clauses)
