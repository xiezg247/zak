"""Repository 当前用户 id。"""

from __future__ import annotations

from vnpy_ashare.storage.auth.users import get_or_create_default_user_id
from vnpy_common.auth.context import get_current_user_id


def get_user_id() -> str:
    uid = get_current_user_id()
    if uid:
        return uid
    return get_or_create_default_user_id()
