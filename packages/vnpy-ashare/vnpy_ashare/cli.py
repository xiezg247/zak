"""vnpy_ashare CLI 实现（zak 仓库入口见根目录 cli.py）。"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv


def bootstrap_runtime() -> None:
    """加载 .env 并将工作目录切到仓库根（sys.path 由 vnpy_ashare.__init__ 注入）。"""
    from vnpy_common.paths import ENV_FILE, resolve_project_root

    root = resolve_project_root()
    os.environ.setdefault("ZAK_PROJECT_ROOT", str(root))
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    os.chdir(root)
    load_dotenv(ENV_FILE)


bootstrap_runtime()


from vnpy_ashare.commands import data as data_commands
from vnpy_ashare.commands import diagnose as diagnose_commands
from vnpy_ashare.commands import jobs as jobs_commands
from vnpy_ashare.commands import meta as meta_commands
from vnpy_ashare.commands import notes as notes_commands
from vnpy_ashare.commands import quotes as quotes_commands
from vnpy_ashare.commands import recipe as recipe_commands
from vnpy_ashare.commands import screener as screener_commands
from vnpy_ashare.commands import skills as skills_commands
from vnpy_ashare.commands import tools as tools_commands


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zak", description="zak A 股终端命令行")
    subparsers = parser.add_subparsers(dest="command", required=True)

    jobs_commands.register(subparsers)
    screener_commands.register(subparsers)
    recipe_commands.register(subparsers)
    data_commands.register(subparsers)
    meta_commands.register(subparsers)
    notes_commands.register(subparsers)
    quotes_commands.register(subparsers)
    tools_commands.register(subparsers)
    skills_commands.register(subparsers)
    diagnose_commands.register(subparsers)

    return parser


def main(argv: list[str] | None = None) -> int:
    bootstrap_runtime()
    parser = _build_parser()
    args = parser.parse_args(argv)
    return int(args.handler(args))


if __name__ == "__main__":
    raise SystemExit(main())
