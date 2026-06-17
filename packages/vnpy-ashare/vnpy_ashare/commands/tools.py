"""运维与调试工具。"""

from __future__ import annotations

import argparse

from vnpy.trader.database import get_database
from vnpy.trader.setting import SETTINGS

from vnpy_mcp.config import load_all_mcp_servers
from vnpy_mcp.remote import McpClientError, list_remote_tools


def _cmd_mcp_list(_args: argparse.Namespace) -> int:

    configs = load_all_mcp_servers()
    if not configs:
        print("未找到 MCP 配置，请复制 mcp/mcp.json.example → mcp/mcp.json")
        return 1

    any_ok = False
    for name, config in sorted(configs.items()):
        print(f"\n=== {name} ===")
        if not config.available:
            print(f"  不可用：{', '.join(config.missing_hints)}")
            continue
        if not config.enabled:
            print("  已禁用")
            continue
        try:
            tools = list_remote_tools(config.url, config.headers, timeout=30)
        except McpClientError as ex:
            print(f"  连接失败：{ex}")
            continue
        any_ok = True
        for tool in tools:
            desc = (tool.description or "").replace("\n", " ")[:100]
            print(f"  {tool.name}\t{desc}")
        print(f"  共 {len(tools)} 个工具")
        print(f"  LLM 调用名：mcp_{name}_<tool.name>")

    return 0 if any_ok else 2


def _cmd_db_check(_args: argparse.Namespace) -> int:
    name = SETTINGS.get("database.name", "sqlite")
    print(f"database.name = {name}")

    if name == "postgresql":
        print(f"  host={SETTINGS.get('database.host')} port={SETTINGS.get('database.port')}")

    db = get_database()
    overviews = db.get_bar_overview()
    print(f"连接成功，本地日 K 概览 {len(overviews)} 条")
    return 0


def register(subparsers: argparse._SubParsersAction) -> None:
    tools = subparsers.add_parser("tools", help="运维与调试")
    tools_sub = tools.add_subparsers(dest="tools_command", required=True)

    mcp = tools_sub.add_parser("mcp-list", help="列出已配置 MCP Server 的远端工具")
    mcp.set_defaults(handler=_cmd_mcp_list)

    db = tools_sub.add_parser("db-check", help="检查 K 线数据库连接")
    db.set_defaults(handler=_cmd_db_check)
