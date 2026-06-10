# vnpy_llm

VeighNa **LLM 对话插件**：流式对话、Agent Skill、MCP 工具、Trace。

## 加载

```python
from vnpy_llm import LlmApp

main_engine.add_app(LlmApp)
```

## 包结构

```
vnpy_llm/
├── app/           # LlmApp 插件、LlmEngine
├── config/        # LlmConfig、load_llm_config
├── chat/          # OpenAI 客户端、ChatStore、SessionSurface
├── routing/       # 意图识别、路由、Prompt
├── tools/         # 工具审计、labels、result enrich、状态
├── trace/         # TurnTrace 内存态与 SQLite 持久化
└── ui/
    ├── panel/     # 主对话面板、Worker、Markdown 渲染
    ├── floating/  # 悬浮球与精简面板
    ├── session/   # 会话侧栏
    ├── dialogs/   # 工具状态与审计
    ├── trace/     # Trace 内联组件
    ├── styles/
    └── themed_styles.py
```

## 核心入口

| 路径 | 说明 |
|------|------|
| `app/engine.py` | LlmEngine（会话、流式、工具调用） |
| `chat/store.py` | 对话 SQLite（`llm_chat.db`） |
| `routing/router.py` | 意图路由与 tool 选择 |
| `ui/panel/chat.py` | AiChatPanel（Dock / 全屏） |

依赖 `vnpy-common`（AI 协议、主题）、`vnpy-skills`、`vnpy-mcp`。
