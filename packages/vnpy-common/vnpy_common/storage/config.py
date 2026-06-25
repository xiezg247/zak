"""数据库连接配置：业务库仅 PostgreSQL（DATABASE_URL）。"""

from __future__ import annotations

import os
from typing import Literal
from urllib.parse import quote_plus

DatabaseDriver = Literal["postgresql"]

_forced_url: str | None = None
_dotenv_loaded = False

_PG_REQUIRED_MSG = "未配置 PostgreSQL。请在 .env 设置 DATABASE_URL，或配置 POSTGRES_HOST / POSTGRES_USER / POSTGRES_DATABASE。"


def reset_storage_config() -> None:
    """测试 teardown：恢复默认配置。"""
    global _forced_url, _dotenv_loaded
    _forced_url = None
    _dotenv_loaded = False
    # 重置连接池
    from vnpy_common.storage.pool import reset_engine

    reset_engine()
    # 重置缓存
    try:
        from vnpy_ashare.storage.auth import users as users_module

        users_module._cached_default_user_id = None
        users_module._cached_default_user_db = None
    except ImportError:
        pass
    try:
        from vnpy_common.storage import session as session_module

        session_module._migration_done = False
    except ImportError:
        pass


def force_database_url(url: str) -> None:
    """测试注入：强制 PostgreSQL 连接串。"""
    global _forced_url
    _forced_url = url.strip()


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _ensure_dotenv() -> None:
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    try:
        from dotenv import load_dotenv

        from vnpy_common.paths import ENV_FILE

        if ENV_FILE.is_file():
            load_dotenv(ENV_FILE, override=False)
    except ImportError:
        pass
    _dotenv_loaded = True


def resolve_database_url() -> str | None:
    _ensure_dotenv()
    if _forced_url:
        return _forced_url
    direct = _env("DATABASE_URL")
    if direct:
        return direct
    keys = ("POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DATABASE")
    if not any(_env(key) for key in keys):
        return None
    host = _env("POSTGRES_HOST") or "localhost"
    port = _env("POSTGRES_PORT") or "5432"
    user = _env("POSTGRES_USER") or "zak"
    password = _env("POSTGRES_PASSWORD") or "zak"
    database = _env("POSTGRES_DATABASE") or "zak"
    user_q = quote_plus(user)
    password_q = quote_plus(password)
    return f"postgresql://{user_q}:{password_q}@{host}:{port}/{database}"


def require_database_url() -> str:
    url = resolve_database_url()
    if not url:
        raise RuntimeError(_PG_REQUIRED_MSG)
    return url


def database_driver() -> DatabaseDriver:
    require_database_url()
    return "postgresql"


def is_postgresql() -> bool:
    """业务库恒为 PostgreSQL（保留 API 兼容）。"""
    return True


APP_SEARCH_PATH = "app, chat, auth, cache, system, public"
