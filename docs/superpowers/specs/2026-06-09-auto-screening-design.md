# 全自动选股设计说明

**日期**：2026-06-09  
**状态**：待实施  
**范围**：AI 助手（悬浮 / Dock / 全屏共用）对话内直接执行选股

---

## 背景

当前选股链路：

1. AI 调用 `propose_screening` → 生成草案
2. 用户点确认框「确认运行」
3. `run_screener` 执行 → 结果写入 `context_store` + 选股页

`screen_by_condition` 在 Skill 层被硬禁用；`ScreeningService` / `runner.run_screener` 已具备 Redis + Tushare 回退能力，但未接到 AI 对话的「一键执行」路径。

## 目标

用户在 AI 对话中说「今天涨幅前 20」时，**无需确认框**，直接在对话中返回 Markdown 表格结果；复杂/模糊条件仍走 `propose_screening` 确认流程。

## 非目标

- 不改变选股页 GUI 主流程
- 不删除 `propose_screening` 确认机制
- 不在本阶段实现形态选股（老鸭头等）的全自动规则引擎——仍走 TDX MCP 轻量查询或 `propose_screening`

---

## 方案：双轨选股（推荐）

| 路径 | 工具 | 触发条件 |
|------|------|----------|
| **自动** | `screen_by_condition` | 内置 preset 可解析；`confidence` 为 high/medium；无 `scheme_name`；非形态/技术复合条件 |
| **确认** | `propose_screening` | 已保存方案；`confidence=low`；意图模糊；形态/多因子复合需 MCP 探查 |

### 自动轨可执行范围

- 7 个内置 preset：涨幅榜、换手率排行、成交量放大、自定义筛选、低 PE、中大盘、主力净流入
- 自定义筛选：须带明确数值阈值（`min_change_pct` / `max_change_pct` / `min_turnover`）
- `top_n`：1–200，默认 20

### 仍须确认的场景

- `scheme_name` / 「我的 · xxx」已保存方案
- 路由 `clarification_needed=true` 或 `confidence=low`
- 形态选股快捷菜单（老鸭头、W 底等）—— prompt 引导 MCP 探查 + `propose_screening`

---

## 数据流

```text
用户消息
  → 意图路由（screening + ScreeningIntent）
  → LLM 选择工具
       ├─ screen_by_condition(name, top_n, …)
       │     → nl_mapper 校验（复用 normalize / clamp）
       │     → runner.run_screener(ScreenerRequest)
       │     → load_screening_quote_snapshot()（交易时段 Redis / 非交易 Tushare 回退）
       │     → ScreeningService.persist_run_result()
       │     → JSON 结果返回对话（AI 转 Markdown 表格）
       └─ propose_screening(…)
             → 草案 → 确认框（现有流程不变）
```

### 与现有执行路径对齐

- **统一走 `runner.run_screener`**，不再在 Skill 内分叉 `screen_quote_preset`（后者缺少非交易时段 Tushare 回退）
- 自动执行后同样写入 `context_store` + `save_run`，使 `get_screening_context` 与选股页上下文可用

---

## 接口变更

### `screen_by_condition` 工具参数（扩展）

```json
{
  "name": "涨幅榜",
  "top_n": 20,
  "min_change_pct": null,
  "max_change_pct": null,
  "min_turnover": null
}
```

### 返回格式

成功：

```json
{
  "status": "ok",
  "condition": "涨幅榜",
  "count": 20,
  "source": "quote",
  "updated_at": "2026-06-09 15:00:00",
  "total_scanned": 5123,
  "results": [{ "symbol": "...", "name": "...", ... }]
}
```

失败（无行情）：

```json
{
  "status": "error",
  "message": "暂无可用的市场行情数据…请先运行行情采集或打开市场页。"
}
```

---

## Prompt / 路由变更摘要

| 文件 | 变更 |
|------|------|
| `vnpy_llm/prompts.py` | 简单内置 preset → `screen_by_condition`；复杂/保存方案 → `propose_screening` |
| `vnpy_llm/routing.py` | screening 工具组加入 `screen_by_condition`；hint 按 confidence 分流 |
| `vnpy_ashare/ai/context.py` | `_screening_prompt` 更新双轨说明 |
| `vnpy_llm/tool_result.py` | 移除对 `screen_by_condition` 的拦截改写 |
| `skills/tdx-stock-picker/SKILL.md` | 场景 B/C 保留确认；场景 A 轻量 builtin 改走 `screen_by_condition` |

---

## 错误处理

| 场景 | 行为 |
|------|------|
| Redis 无数据 | 返回明确错误 + 引导「行情采集」或打开市场页 |
| Tushare token 缺失 | 低 PE 等 tushare preset 返回 error，提示配置 `TUSHARE_TOKEN` |
| 未知 preset | 返回 error + 建议 `list_screeners` |
| 自动轨校验失败 | 返回 `need_confirm` 状态，提示改调 `propose_screening` |

---

## 测试策略

- 单元：`screen_by_condition` 有缓存行情时返回 `ok`；无数据时 `error`；`scheme_name` 类输入走 `need_confirm`
- 路由：`filter_tools_by_route("screening")` 含 `screen_by_condition`；high confidence hint 指向自动轨
- 回归：`propose_screening` 现有测试不变

---

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| LLM 误用自动轨跑复杂条件 | 路由 hint + tool description 明确边界；`need_confirm` 兜底 |
| 结果未落库导致无法解读 | `persist_run_result` 与确认框路径一致 |
| 非交易时段无 Redis | `runner` 已有 Tushare 回退，统一入口即可 |

---

## 验收标准

1. 对话输入「今天涨最多的前 10 只」→ 直接返回表格，无确认框
2. 对话输入「用我的方案 xxx」→ 仍弹确认框
3. 自动执行后 `get_screening_context` 能读到本次结果
4. 悬浮 / Dock / 全屏三种入口行为一致
