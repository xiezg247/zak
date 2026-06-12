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
├── routing/       # 意图识别、路由、Prompt（base_prompt 与 agents 共用）
├── graph/         # LangGraph 编排（Supervisor + Specialist + handoff + HITL）
│   ├── agents/    # 各域 system prompt 切片
│   ├── supervisor.py
│   ├── handoff.py
│   └── hitl.py
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
| `graph/runner.py` | LangGraph 流式 tool loop（`stream_with_tools`） |
| `ui/panel/chat.py` | AiChatPanel（Dock / 全屏） |

依赖 `vnpy-common`（AI 协议、主题）、`vnpy-skills`、`vnpy-mcp`、`langgraph`、`langchain`。

有工具：`routing` 分类 → `graph/runner.stream_with_tools`（`create_agent` ReAct loop）。  
无工具：`chat/client.stream_chat_completion` + `routing/prompts.py`。
