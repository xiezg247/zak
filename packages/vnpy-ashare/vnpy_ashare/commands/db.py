"""数据库 migration 命令。"""

from __future__ import annotations

import argparse
from pathlib import Path

from vnpy_common.paths import get_app_db_path, get_chat_db_path
from vnpy_common.storage.config import require_database_url, resolve_database_url
from vnpy_common.storage.migrate import upgrade_head

from vnpy_ashare.storage.import_legacy import ImportLegacyOptions, import_legacy
from vnpy_ashare.storage.repositories.watchlist_repair import repair_all_watchlist_names


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


def _cmd_import_legacy(args: argparse.Namespace) -> int:
    try:
        require_database_url()
        report = import_legacy(
            ImportLegacyOptions(
                app_db=Path(args.app_db) if args.app_db else None,
                chat_db=Path(args.chat_db) if args.chat_db else None,
                username=args.username,
                dry_run=args.dry_run,
                skip_cache=args.skip_cache,
                cache_only=args.cache_only,
                archive=args.archive,
                upgrade=not args.no_upgrade,
            )
        )
    except RuntimeError as ex:
        print(str(ex))
        return 1

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"{prefix}SQLite → PostgreSQL 导入完成")
    for line in report.summary_lines():
        print(line)
    return 0


def _cmd_repair_watchlist_names(args: argparse.Namespace) -> int:
    try:
        require_database_url()
    except RuntimeError as ex:
        print(str(ex))
        return 1
    legacy_db = Path(args.legacy_db) if args.legacy_db else None
    report = repair_all_watchlist_names(legacy_db=legacy_db, dry_run=args.dry_run)
    for line in report.summary_lines():
        print(line)
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    db = subparsers.add_parser("db", help="PostgreSQL schema 迁移与遗留数据导入")
    db_sub = db.add_subparsers(dest="db_command", required=True)

    upgrade = db_sub.add_parser("upgrade", help="执行 Alembic upgrade head")
    upgrade.set_defaults(handler=_cmd_upgrade)

    status = db_sub.add_parser("status", help="显示当前数据库驱动与连接")
    status.set_defaults(handler=_cmd_status)

    legacy = db_sub.add_parser("import-legacy", help="将本地 SQLite 一次性导入 PostgreSQL")
    legacy.add_argument("--app-db", default="", help=f"业务库路径（默认 {get_app_db_path()}）")
    legacy.add_argument("--chat-db", default="", help=f"对话库路径（默认 {get_chat_db_path()}）")
    legacy.add_argument("--username", default="default", help="遗留数据归属用户名（默认 default）")
    legacy.add_argument("--dry-run", action="store_true", help="仅统计行数，不写入")
    legacy.add_argument("--skip-cache", action="store_true", help="跳过 radar 缓存库")
    legacy.add_argument(
        "--cache-only",
        action="store_true",
        help="仅导入 cache schema（独立 .db + zak.db 内嵌表）；常与 --no-upgrade 联用补导",
    )
    legacy.add_argument("--archive", action="store_true", help="导入成功后将源 SQLite 移至 data/backup/")
    legacy.add_argument("--no-upgrade", action="store_true", help="跳过 db upgrade")
    legacy.set_defaults(handler=_cmd_import_legacy)

    repair = db_sub.add_parser("repair-watchlist-names", help="补全 watchlist 表中缺失的证券名称（一次性修复）")
    repair.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    repair.add_argument(
        "--legacy-db",
        default="",
        help=f"优先从遗留 SQLite 读取名称（默认 {get_app_db_path()}）",
    )
    repair.set_defaults(handler=_cmd_repair_watchlist_names)
