# vnpy_mcp

VeighNa **远端 MCP 工具引擎**：从 `mcp/mcp.json` 加载 Streamable HTTP 服务，发现工具并代理执行。

## 使用

```python
from vnpy_mcp.app.engine import McpEngine

engine = McpEngine()
engine.load_all()
engine.init_providers()
```

## 包结构

```
vnpy_mcp/
├── app/           # McpEngine
├── config/        # mcp.json 加载、内置 Provider 元数据
├── domain/        # McpProvider 基类、McpToolInfo
└── remote/        # Streamable HTTP 客户端、RemoteMcpProvider
```

## 核心入口

| 路径 | 说明 |
|------|------|
| `app/engine.py` | McpEngine（加载、连接、工具索引、执行） |
| `config/settings.py` | `McpServerConfig`、`load_all_mcp_servers` |
| `config/registry.py` | 内置 Provider 元数据（如 tdx） |
| `remote/client.py` | `list_remote_tools`、`call_remote_tool` |
| `remote/provider.py` | JSON 配置驱动的 `RemoteMcpProvider` |

配置目录默认 `mcp/`（可通过 `MCP_DIR` 覆盖）。

依赖 `vnpy-common`（路径）、`vnpy-skills`（ToolSpec 协议）。
