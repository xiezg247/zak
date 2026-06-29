"""数据库 migration 命令。"""

from __future__ import annotations

import argparse

from vnpy_ashare.storage.repositories.watchlist_repair import repair_all_watchlist_names
from vnpy_common.storage.config import require_database_url, resolve_database_url
from vnpy_common.storage.migrate import upgrade_head


def _cmd_upgrade(_args: argparse.Namespace) -> int:
    url = resolve_database_url()
    if not url:
        print("未配置 DATABASE_URL 或 POSTGRES_*，无法升级 PostgreSQL schema。")
        return 1
    upgrade_head()
    print(f"PostgreSQL schema 已升级：{url.split('@')[-1]}")
    return 0


def _cmd_status(_args: argparse.Namespace) -> int:
    try:
        url = require_database_url()
    except RuntimeError as ex:
        print(str(ex))
        return 1
    print(f"驱动: postgresql\n连接: {url}")
    return 0


def _cmd_repair_watchlist_names(args: argparse.Namespace) -> int:
    try:
        require_database_url()
    except RuntimeError as ex:
        print(str(ex))
        return 1
    report = repair_all_watchlist_names(dry_run=args.dry_run)
    for line in report.summary_lines():
        print(line)
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    db = subparsers.add_parser("db", help="PostgreSQL schema 迁移")
    db_sub = db.add_subparsers(dest="db_command", required=True)

    upgrade = db_sub.add_parser("upgrade", help="执行 Alembic upgrade head")
    upgrade.set_defaults(handler=_cmd_upgrade)

    status = db_sub.add_parser("status", help="显示当前数据库驱动与连接")
    status.set_defaults(handler=_cmd_status)

    repair = db_sub.add_parser("repair-watchlist-names", help="补全 watchlist 表中缺失的证券名称")
    repair.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    repair.set_defaults(handler=_cmd_repair_watchlist_names)
