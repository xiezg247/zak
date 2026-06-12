"""多因子配方选股 CLI。"""

from __future__ import annotations

import argparse
import sys

from vnpy_ashare.commands.screener import print_screen_rows
from vnpy_ashare.screener.recipe.recipe import list_recipe_catalog, resolve_recipe
from vnpy_ashare.screener.recipe.recipe_runner import run_recipe
from vnpy_ashare.screener.run.export import export_rows_to_csv
from vnpy_ashare.storage.connection import init_app_db


def _cmd_recipe_list(_args: argparse.Namespace) -> int:
    print("可用多因子配方：")
    for entry in list_recipe_catalog():
        print(f"  {entry.recipe_id:<24} {entry.display_name} ({entry.trigger_kind})")
    return 0


def _cmd_recipe_run(args: argparse.Namespace) -> int:
    init_app_db()
    recipe = resolve_recipe(args.recipe_id)
    if recipe is None:
        print(f"未知配方：{args.recipe_id}", file=sys.stderr)
        return 1

    try:
        result = run_recipe(args.recipe_id, top_n=args.top_n, condition_prefix="CLI")
    except Exception as ex:
        print(f"配方选股失败：{ex}", file=sys.stderr)
        return 1

    print_screen_rows(result)

    if args.export:
        path = export_rows_to_csv(result.rows, args.export)
        print(f"已导出：{path}")

    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    recipe_parser = subparsers.add_parser("recipe", help="多因子配方选股")
    recipe_sub = recipe_parser.add_subparsers(dest="recipe_command", required=True)

    recipe_list = recipe_sub.add_parser("list", help="列出可用配方")
    recipe_list.set_defaults(handler=_cmd_recipe_list)

    recipe_run = recipe_sub.add_parser("run", help="运行配方选股")
    recipe_run.add_argument("recipe_id", help="配方 ID，如 intraday_multi")
    recipe_run.add_argument("--top-n", type=int, help="返回条数，默认使用配方配置")
    recipe_run.add_argument("--export", metavar="PATH", help="导出 CSV 路径")
    recipe_run.set_defaults(handler=_cmd_recipe_run)
