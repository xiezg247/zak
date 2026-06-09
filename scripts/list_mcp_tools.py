#!/usr/bin/env python3
"""列出已配置 MCP Server 的远端工具（用于维护 docs/ai-data-routing.md）。"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> int:
    from vnpy_mcp.client import McpClientError, list_remote_tools
    from vnpy_mcp.config import load_all_mcp_servers

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


if __name__ == "__main__":
    raise SystemExit(main())
