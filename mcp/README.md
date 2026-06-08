# MCP 外接配置

推荐单文件 `mcp/mcp.json`，在 `mcpServers` 里配置多个服务。

```bash
cp mcp/mcp.json.example mcp/mcp.json
# 编辑 mcp/mcp.json，填入各服务的 url / headers
```

## 标准格式

```json
{
  "mcpServers": {
    "tdx": {
      "url": "https://mcp.tdx.com.cn:3001/mcp",
      "headers": {
        "tdx-api-key": "你的密钥"
      }
    },
    "my-data": {
      "url": "https://example.com/mcp",
      "headers": {
        "Authorization": "Bearer token"
      }
    }
  }
}
```

## 配置文件查找顺序

后加载的同名 Provider 覆盖先加载的：

| 顺序 | 文件 | 说明 |
|------|------|------|
| 1 | `mcp.json`（项目根） | legacy |
| 2 | `mcp/mcp.json` | **推荐** |
| 3 | `mcp/<name>.json` | 可选单服务扩展 |

环境变量：

- `MCP_CONFIG_PATH`：指定单个配置文件路径（跳过自动查找）
- `MCP_DIR`：配置目录，默认 `./mcp`

## 单文件扩展（可选）

除 `mcp/mcp.json` 外，也可在 `mcp/` 下放置单服务文件（会覆盖同名项）：

```
mcp/
  mcp.json          # 主配置（多服务）
  tdx.json          # 可选：单独覆盖 tdx
  broker.example.json
```

`*.example.json` 与 `_*.json` 不会被加载。
