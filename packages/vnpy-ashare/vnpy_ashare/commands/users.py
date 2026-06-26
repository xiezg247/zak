"""用户账号 CLI。"""

from __future__ import annotations

import argparse

from vnpy_ashare.storage.auth.prune_users import prune_to_default_user
from vnpy_ashare.storage.auth.users import create_user, list_users
from vnpy_ashare.storage.connection import connect


def _cmd_create(args: argparse.Namespace) -> int:
    with connect() as conn:
        user = create_user(conn, username=args.username, password=args.password, display_name=args.display_name or args.username)
    print(f"已创建用户：{user.username} ({user.id})")
    print("提示：创建第二个用户后，启动时将弹出登录框。")
    return 0


def _cmd_list(_args: argparse.Namespace) -> int:
    with connect() as conn:
        users = list_users(conn)
    if not users:
        print("暂无用户")
        return 0
    for user in users:
        label = user.display_name or user.username
        print(f"{user.username}\t{label}\t{user.id}")
    return 0


def _cmd_prune(_args: argparse.Namespace) -> int:
    report = prune_to_default_user()
    for line in report.summary_lines():
        print(line)
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    user_parser = subparsers.add_parser("user", help="用户账号管理")
    user_sub = user_parser.add_subparsers(dest="user_command", required=True)

    create_cmd = user_sub.add_parser("create", help="创建用户（多用户时启动需登录）")
    create_cmd.add_argument("username", help="用户名")
    create_cmd.add_argument("password", help="密码")
    create_cmd.add_argument("--display-name", default="", help="显示名")
    create_cmd.set_defaults(handler=_cmd_create)

    list_cmd = user_sub.add_parser("list", help="列出用户")
    list_cmd.set_defaults(handler=_cmd_list)

    prune_cmd = user_sub.add_parser("prune", help="删除 default 以外的用户及其私有数据")
    prune_cmd.set_defaults(handler=_cmd_prune)
