"""chat schema Repository 基类。"""

from __future__ import annotations

from sqlalchemy.sql.elements import ColumnElement

from vnpy_ashare.storage.auth.scope import get_user_id
from vnpy_common.storage.query import user_scope
from vnpy_common.storage.repository import UserScopedRepository


class ChatUserScopedRepository(UserScopedRepository):
    """绑定 chat schema 用户隔离。"""

    @staticmethod
    def user_id_resolver() -> str:
        return get_user_id()

    def prepare(self) -> None:
        """表由 Alembic 管理，无需 inline DDL。"""

    def scope_table(self, table, *extras: ColumnElement[bool]) -> ColumnElement[bool]:
        """对任意带 user_id 的 chat 表生成当前用户过滤。"""
        return user_scope(table.c.user_id, self.current_user_id(), *extras)
