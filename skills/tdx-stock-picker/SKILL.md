---
name: tdx-stock-picker
description: 通达信 AI 选股技能。利用通达信 MCP 提供的行情、财务、技术指标、板块、研报等工具，按用户意图组合多条件筛选 A 股标的。与终端自建选股页协同：盘中/盘后多因子直接 run_recipe；内置 preset / 已保存方案直接 screen_by_condition；形态用 screen_by_pattern。选股直接执行，无需用户二次确认。
author: zak
version: 1.0.0
---

# tdx-stock-picker

把自然语言选股需求，转成**终端 Skill 工具**调用（非 Python 脚本）。

> **重要**：本 Skill 包**只有 SKILL.md 文档**，没有 `tdx_stock_picker.py` 等可 import 模块。
> **禁止** `run_python(skill="tdx-stock-picker", ...)` 或 `from tdx_stock_picker import ...`。
> 执行选股请直接调用下方「终端本地工具」。

## What this skill is for

- "最近哪些票在涨？"
- "帮我找 PE < 15、ROE > 20% 的票"
- "有没有放量突破前高的？"
- "主力资金在买哪些板块？"
- "今天有哪些低价股异动？"
- "选几只技术面走好的，我看看"

先理解用户想要什么维度的筛选，再决定调用哪个终端工具（见下表）。

---

## 工具盘点

### 终端 Skill 工具（执行选股必须用这些）

| 用户意图 | 调用工具 | 示例 |
|----------|----------|------|
| 形态：老鸭头 / 均线多头 / W底 / 热点 | `screen_by_pattern` | `pattern="均线多头排列"` |
| 盘中/盘后多因子 | `run_recipe` | `recipe_id="intraday_multi"` |
| 内置 preset（涨幅榜、低 PE 等） | `screen_by_condition` | `name="低 PE"` |
| 了解可用方案 | `list_screeners` / `list_recipes` | — |
| 解读选股结果 | `explain_screening_run` | — |

**形态名对照**（传给 `screen_by_pattern` 的 `pattern` 参数）：

| 说法 | pattern 值 |
|------|------------|
| 老鸭头 | `老鸭头形态` |
| 均线多头 / 多头排列 | `均线多头排列` |
| W底 / 双底 | `W底形态` |
| 热点 / 高换手活跃 | `主题投资` |

### 通达信 MCP（Skill 内部使用，LLM 勿直接调用）

形态扫描、综合诊断等场景由 `screen_by_pattern`、`diagnose_stock` 等终端工具**内部**调用 MCP；
失败时自动降级本地日 K。**不要**自行 `run_python` 或调用 `mcp_tdx_*`。

---

## 工作流

### 场景 A：形态 / preset / 配方（直接执行）

1. 形态选股 → **`screen_by_pattern`**（如均线多头：`pattern="均线多头排列", top_n=20`）
2. 内置 preset → **`screen_by_condition`**
3. 多因子配方 → **`run_recipe`**
4. 用 Markdown 表格返回结果，默认 Top 20，排除 ST

### 场景 B：条件复杂或需落库

1. `list_screeners` / `list_recipes` 了解方案
2. 按上表选择工具直接执行
3. 结果写入选股页，可用 `explain_screening_run` 解读

### 场景 C：财务 / 宏观数据研究

走 **tushare-data** Skill 的 `run_python`，与本 Skill 无关。

---

## 常见选股模式（映射到工具）

### 趋势追踪 / 技术突破 / 均线多头

→ **`screen_by_pattern(pattern="均线多头排列")`**

### 价值发现（低 PE）

→ **`screen_by_condition(name="低 PE")`**

### 资金异动 / 盘中多因子

→ **`run_recipe(recipe_id="intraday_multi")`**

### 板块轮动

→ **`run_recipe(recipe_id="intraday_multi")`**（含板块维度）

---

## 注意事项

1. **禁止 run_python**：本 Skill 无 Python 模块；选股一律用终端 Skill 工具
2. **禁止编造 import**：不存在 `tdx_stock_picker`、`screen_by_pattern` Python 包
3. **ST 处理**：除非用户明确要求，默认排除 ST
4. **结果数量**：默认 Top 20
5. **交互先行**：条件模糊时先追问
