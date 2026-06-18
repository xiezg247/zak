# vnpy_llm

VeighNa **LLM 对话插件**：流式对话、Agent Skill、MCP 工具、Trace。

## 加载

```python
from vnpy_llm.app.plugin import LlmApp

main_engine.add_app(LlmApp)
```

## 包结构

```
vnpy_llm/
├── gateway/       # Agent 控制面（编排唯一入口）
│   ├── agent_gateway.py    # send / cancel / subscribe
│   ├── agent_runtime.py    # 有工具 / 无工具流式 runtime
│   ├── routing_plane.py    # router + supervisor 一层
│   ├── session_manager.py  # 会话与 surface 双轨
│   ├── trace_coordinator.py
│   ├── tool_registry.py    # Skill + MCP
│   ├── context_assembler.py
│   └── types.py            # AgentEvent、SendRequest
├── app/           # LlmApp 插件、LlmEngine（Qt 桥接）
├── config/        # LlmConfig、load_llm_config
├── chat/          # OpenAI 客户端、ChatStore、SessionSurface
├── routing/       # 意图识别、路由、Prompt（base_prompt 与 agents 共用）
├── graph/         # LangGraph 编排（Supervisor + Specialist + handoff）
│   ├── agents/    # 各域 system prompt 切片
│   ├── supervisor.py
│   └── handoff.py
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
| `gateway/agent_gateway.py` | **AgentGateway**：会话、上下文、工具、流式回复、事件订阅 |
| `app/engine.py` | **LlmEngine**：委托 Gateway，`AgentEvent` → Qt 信号 |
| `chat/store.py` | 对话 SQLite（`llm_chat.db`） |
| `routing/router.py` | 意图分类与 tool 子集（由 `RoutingPlane` 调用） |
| `graph/runner.py` | LangGraph 流式 tool loop（由 `AgentRuntime` 调用） |
| `ui/panel/chat.py` | AiChatPanel（Dock / 全屏） |

依赖 `vnpy-common`（AI 协议、主题）、`vnpy-skills`、`vnpy-mcp`、`langgraph`、`langchain`。

## 对话流程

```
AgentGateway.send(SendRequest)
  → RoutingPlane.route()          # 有工具时
  → AgentRuntime.stream_deltas()  # agent 或 chat 路径
  → ToolRegistry.execute()        # 工具回调内
```

有工具：`RoutingPlane` → `graph/runner.stream_with_tools`（`create_agent` ReAct loop）。  
无工具：`chat/client.stream_chat_completion` + `ContextAssembler.build_api_messages`。

UI 经 `LlmEngine.stream_reply` 调用，内部等价于 `gateway.send`。

## 事件订阅

```python
from vnpy_llm.gateway.types import AgentEvent, AgentEventType

def on_event(event: AgentEvent) -> None:
    if event.type == AgentEventType.CHAT_DELTA:
        print(event.payload["delta"])

unsub = gateway.subscribe(on_event)
```

`LlmEngine` 在初始化时将上述事件映射为 `LlmSignals`（`stream_delta`、`tool_call_started` 等）。
