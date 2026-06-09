# 全自动选股 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 AI 对话（悬浮 / Dock / 全屏共用）中，对简单内置选股条件实现 `screen_by_condition` 一键执行并返回结果；复杂条件保留 `propose_screening` 确认流程。

**Architecture:** 双轨分流——`nl_mapper` 新增 `resolve_auto_screen_request()` 校验自动轨资格；`screen_by_condition` 统一委托 `runner.run_screener()`；`ScreeningService.persist_run_result()` 复用确认框落库逻辑。路由与 System Prompt 按 confidence 引导工具选择。

**Tech Stack:** Python 3.11+、vnpy_skills、vnpy_ashare/screener、vnpy_llm、pytest

**设计文档：** [2026-06-09-auto-screening-design.md](../specs/2026-06-09-auto-screening-design.md)

---

## 文件结构

| 文件 | 职责 |
|------|------|
| `vnpy_ashare/screener/auto_screen.py` | **新建** 自动轨资格判断 + Request 解析 |
| `vnpy_ashare/services/screening_service.py` | 新增 `persist_run_result()` |
| `skills/vnpy_screening_skill.py` | 恢复 `screen_by_condition` 执行逻辑 |
| `vnpy_llm/routing.py` | 工具组 + routing hint 分流 |
| `vnpy_llm/prompts.py` | System Prompt 双轨说明 |
| `vnpy_ashare/ai/context.py` | 全屏快捷指令 prompt 更新 |
| `vnpy_llm/tool_result.py` | 移除 screen_by_condition 拦截 |
| `skills/tdx-stock-picker/SKILL.md` | 工作流文档更新 |
| `tests/test_auto_screen.py` | **新建** 自动轨解析测试 |
| `tests/test_vnpy_screening_skill.py` | 更新 screen_by_condition 测试 |
| `tests/llm/test_routing.py` | 更新 routing 测试 |

---

### Task 1: 自动轨解析模块

**Files:**
- Create: `vnpy_ashare/screener/auto_screen.py`
- Test: `tests/test_auto_screen.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/test_auto_screen.py
from vnpy_ashare.screener.auto_screen import resolve_auto_screen_request, AutoScreenInput

def test_builtin_preset_ok():
    result = resolve_auto_screen_request(
        AutoScreenInput(name="涨幅榜", top_n=10)
    )
    assert result.ok is True
    assert result.request.preset == "涨幅榜"
    assert result.request.top_n == 10

def test_saved_scheme_need_confirm():
    result = resolve_auto_screen_request(
        AutoScreenInput(name="我的 · 测试方案")
    )
    assert result.ok is False
    assert result.need_confirm is True

def test_custom_with_threshold_ok():
    result = resolve_auto_screen_request(
        AutoScreenInput(
            name="自定义筛选",
            top_n=20,
            min_change_pct=3.0,
            min_turnover=1.0,
        )
    )
    assert result.ok is True
    assert result.request.min_change_pct == 3.0

def test_unknown_preset_error():
    result = resolve_auto_screen_request(
        AutoScreenInput(name="不存在方案")
    )
    assert result.ok is False
    assert result.error
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_auto_screen.py -v
```

Expected: FAIL `ModuleNotFoundError: vnpy_ashare.screener.auto_screen`

- [ ] **Step 3: 实现解析模块**

```python
# vnpy_ashare/screener/auto_screen.py
"""自动选股轨：资格判断与 Request 解析。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy_ashare.screener.nl_mapper import clamp_top_n, normalize_preset_name
from vnpy_ashare.screener.presets import SCREENER_CUSTOM, get_preset
from vnpy_ashare.screener.runner import ScreenerRequest


@dataclass(frozen=True)
class AutoScreenInput:
    name: str
    top_n: int = 20
    min_change_pct: float | None = None
    max_change_pct: float | None = None
    min_turnover: float | None = None


@dataclass
class AutoScreenResult:
    ok: bool
    request: ScreenerRequest | None = None
    need_confirm: bool = False
    error: str = ""


def resolve_auto_screen_request(data: AutoScreenInput) -> AutoScreenResult:
    name = (data.name or "").strip()
    if not name:
        return AutoScreenResult(ok=False, error="name 不能为空")

    if name.startswith("我的 · "):
        return AutoScreenResult(
            ok=False,
            need_confirm=True,
            error="已保存方案须通过 propose_screening 确认后执行。",
        )

    preset_name = normalize_preset_name(name)
    if not preset_name:
        return AutoScreenResult(ok=False, error=f"未知选股条件「{name}」")

    preset = get_preset(preset_name)
    if preset is None:
        return AutoScreenResult(ok=False, error=f"未知选股条件「{preset_name}」")

    top_n = clamp_top_n(data.top_n)
    if preset.name == SCREENER_CUSTOM:
        if (
            data.min_change_pct is None
            and data.max_change_pct is None
            and data.min_turnover is None
        ):
            return AutoScreenResult(
                ok=False,
                need_confirm=True,
                error="自定义筛选须指定涨幅或换手率阈值，或改用 propose_screening。",
            )
        request = ScreenerRequest(
            preset=preset.name,
            top_n=top_n,
            min_change_pct=data.min_change_pct,
            max_change_pct=data.max_change_pct,
            min_turnover=data.min_turnover,
        )
    else:
        request = ScreenerRequest(preset=preset.name, top_n=top_n)

    return AutoScreenResult(ok=True, request=request)
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_auto_screen.py -v
```

Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add vnpy_ashare/screener/auto_screen.py tests/test_auto_screen.py
git commit -m "feat(screener): 新增自动选股轨解析模块"
```

---

### Task 2: ScreeningService 落库复用

**Files:**
- Modify: `vnpy_ashare/services/screening_service.py`

- [ ] **Step 1: 新增 persist_run_result**

在 `ScreeningService` 类中 `publish_page_context` 之前添加：

```python
    def persist_run_result(
        self,
        result: ScreenerRunResult,
        *,
        nl_source: str = "",
        draft_id: str = "",
    ) -> None:
        """自动/确认选股执行后统一落库（context_store + run_store）。"""
        from vnpy_ashare.screener.run_store import save_run

        rows = list(result.rows)
        self.set_screening_results(
            condition=result.condition,
            rows=rows,
            updated_at=result.updated_at,
        )
        config: dict = {}
        if nl_source:
            config["nl_source"] = nl_source
        if draft_id:
            config["draft_id"] = draft_id
        save_run(
            condition=result.condition,
            source=result.source,
            rows=rows,
            total_scanned=result.total_scanned,
            config=config or None,
        )
        self.publish_page_context()
```

- [ ] **Step 2: 重构确认框调用（可选薄改）**

`vnpy_ashare/ui/screener_confirm_dialog.py` 的 `_on_run_finished` 中，将 `set_screening_results` + `save_run` + `sync_screener_page_context` 替换为：

```python
        if service is not None:
            config_extra = {}
            if draft is not None:
                config_extra["nl_source"] = draft.natural_language
                config_extra["draft_id"] = self.draft_id
            service.persist_run_result(result, nl_source=config_extra.get("nl_source", ""), draft_id=config_extra.get("draft_id", ""))
        else:
            # 保留原有 fallback
            ...
```

> 若确认框改动面较大，可本 Task 仅新增方法，确认框重构放到 Task 6 一并做。

- [ ] **Step 3: Commit**

```bash
git add vnpy_ashare/services/screening_service.py
git commit -m "feat(screening): 统一选股结果落库入口 persist_run_result"
```

---

### Task 3: 恢复 screen_by_condition 执行

**Files:**
- Modify: `skills/vnpy_screening_skill.py`
- Modify: `tests/test_vnpy_screening_skill.py`

- [ ] **Step 1: 更新失败测试**

替换 `test_screen_by_condition_no_data`：

```python
def test_screen_by_condition_no_data():
    from vnpy_ashare.ai.context_store import clear_all

    clear_all()
    svc = MagicMock()
    svc.run_request.side_effect = RuntimeError("暂无可用的市场行情数据")
    skill = _make_skill(svc)
    result = json.loads(skill.screen_by_condition("涨幅榜"))
    assert result["status"] == "error"


def test_screen_by_condition_ok():
    from vnpy_ashare.screener.runner import ScreenerRunResult

    svc = MagicMock()
    svc.run_request.return_value = ScreenerRunResult(
        rows=[{"symbol": "000001", "name": "平安银行", "vt_symbol": "000001.SZSE", "change_pct": 5.2}],
        condition="涨幅榜",
        updated_at="2026-06-09",
        total_scanned=100,
        source="quote",
    )
    skill = _make_skill(svc)
    result = json.loads(skill.screen_by_condition("涨幅榜", top_n=5))
    assert result["status"] == "ok"
    assert result["count"] == 1
    svc.persist_run_result.assert_called_once()


def test_screen_by_condition_need_confirm():
    skill = _make_skill(MagicMock())
    result = json.loads(skill.screen_by_condition("我的 · 测试"))
    assert result["status"] == "need_confirm"
    assert "propose_screening" in result["message"]
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_vnpy_screening_skill.py::test_screen_by_condition_ok -v
```

Expected: FAIL（status 为 blocked）

- [ ] **Step 3: 更新 ToolSpec 与实现**

`register_tools()` 中 `screen_by_condition` 的 description 改为：

```python
description=(
    "直接执行内置选股方案并返回结果（无需用户确认）。"
    "适用于涨幅榜/换手率/低PE等内置 preset；"
    "已保存方案或复杂条件请改用 propose_screening。"
),
parameters={
    "type": "object",
    "properties": {
        "name": {"type": "string", "description": "内置选股方案名"},
        "top_n": {"type": "integer", "description": "返回前 N 条，默认 20"},
        "min_change_pct": {"type": "number", "description": "最小涨幅%，仅自定义筛选"},
        "max_change_pct": {"type": "number", "description": "最大涨幅%，仅自定义筛选"},
        "min_turnover": {"type": "number", "description": "最小换手率%，仅自定义筛选"},
    },
    "required": ["name"],
},
```

`screen_by_condition` 方法替换为：

```python
    def screen_by_condition(
        self,
        name: str,
        top_n: int = 20,
        min_change_pct: float | None = None,
        max_change_pct: float | None = None,
        min_turnover: float | None = None,
    ) -> str:
        from vnpy_ashare.screener.auto_screen import AutoScreenInput, resolve_auto_screen_request

        resolved = resolve_auto_screen_request(
            AutoScreenInput(
                name=name,
                top_n=top_n,
                min_change_pct=min_change_pct,
                max_change_pct=max_change_pct,
                min_turnover=min_turnover,
            )
        )
        if resolved.need_confirm:
            return json.dumps(
                {
                    "status": "need_confirm",
                    "message": resolved.error or "请改用 propose_screening 生成草案并等待用户确认。",
                },
                ensure_ascii=False,
            )
        if not resolved.ok or resolved.request is None:
            return json.dumps(
                {"status": "error", "message": resolved.error or "无法执行选股"},
                ensure_ascii=False,
            )

        svc = self._get_screening_service()
        try:
            result = svc.run_request(resolved.request)
        except Exception as ex:
            return json.dumps({"status": "error", "message": str(ex)}, ensure_ascii=False)

        if not result.rows:
            return json.dumps(
                {
                    "status": "ok",
                    "condition": result.condition,
                    "count": 0,
                    "message": f"选股条件「{result.condition}」未匹配到标的",
                },
                ensure_ascii=False,
            )

        svc.persist_run_result(result, nl_source=f"auto:{name}")
        payload = {
            "status": "ok",
            "condition": result.condition,
            "count": len(result.rows),
            "source": result.source,
            "updated_at": result.updated_at,
            "total_scanned": result.total_scanned,
            "results": [
                {
                    "symbol": r.get("symbol", ""),
                    "name": r.get("name", ""),
                    "vt_symbol": r.get("vt_symbol", ""),
                    "last_price": r.get("last_price"),
                    "change_pct": r.get("change_pct"),
                    "turnover_rate": r.get("turnover_rate"),
                    "pe_ttm": r.get("pe_ttm"),
                    "total_mv": r.get("total_mv"),
                    "net_mf_amount": r.get("net_mf_amount"),
                }
                for r in result.rows
            ],
        }
        return json.dumps(payload, ensure_ascii=False)
```

同步更新 `list_screeners` 的 note：

```python
"note": "简单内置方案可直接 screen_by_condition；复杂/保存方案用 propose_screening。",
```

- [ ] **Step 4: 运行测试**

```bash
pytest tests/test_vnpy_screening_skill.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/vnpy_screening_skill.py tests/test_vnpy_screening_skill.py
git commit -m "feat(screening): 恢复 screen_by_condition 自动执行选股"
```

---

### Task 4: 路由与 Prompt 分流

**Files:**
- Modify: `vnpy_llm/routing.py`
- Modify: `vnpy_llm/prompts.py`
- Modify: `vnpy_llm/tool_result.py`
- Modify: `vnpy_ashare/ai/context.py`
- Modify: `tests/llm/test_routing.py`

- [ ] **Step 1: routing 工具组**

`TOOL_GROUPS["screening"]` 加入 `"screen_by_condition"`：

```python
    "screening": frozenset({
        "list_screeners",
        "screen_by_condition",
        "propose_screening",
        "get_screening_context",
    }),
```

`build_routing_hint` 中 screening 分支改为：

```python
        if s.clarification_needed:
            lines.append("- 意图不够明确，请先向用户追问，勿调用选股工具")
        elif s.confidence == "high" and s.preset and not s.scheme_name:
            lines.append(
                f"- 内置方案「{s.preset}」可直接调用 screen_by_condition（name={s.preset}, top_n={s.top_n}）"
            )
        elif s.confidence in ("high", "medium"):
            lines.append(
                "- 请调用 propose_screening，并传入上述 intent/preset/top_n 等参数"
            )
```

- [ ] **Step 2: 更新 routing 测试**

```python
def test_filter_screening_subset():
    filtered = filter_tools_by_route(ALL_TOOLS, "screening")
    names = {t["function"]["name"] for t in filtered}
    assert "screen_by_condition" in names
    assert "propose_screening" in names

def test_build_routing_hint_auto_screen():
    analysis = IntentAnalysis(
        route=IntentRoute(category="screening", confidence="high"),
        screening=ScreeningIntent(
            intent="涨幅榜前20",
            preset="涨幅榜",
            top_n=20,
            confidence="high",
        ),
    )
    hint = build_routing_hint(analysis)
    assert "screen_by_condition" in hint
```

`ALL_TOOLS` 列表加入 `_tool("screen_by_condition")`。

- [ ] **Step 3: prompts.py**

将第 50 行改为：

```python
- 选股：list_screeners；内置 preset（涨幅榜/换手率/低PE等）且意图明确时直接 screen_by_condition；已保存方案、自定义复合条件或意图模糊时 propose_screening 生成草案待用户确认
```

`SCREENING_PAGE_PROMPT` 第 77 行补充：

```python
若条件简单且为内置 preset，可 screen_by_condition 直接执行；否则 propose_screening 并等待确认。
```

- [ ] **Step 4: tool_result.py**

删除这一行：

```python
    (r"screen_by_condition", "请改用 propose_screening 生成草案，待用户在确认框中确认后再执行"),
```

- [ ] **Step 5: context.py `_screening_prompt`**

```python
        f"请按「{intent}」在 A 股中选股。{extra}"
        "先 list_screeners 了解终端内置方案；"
        "内置 preset 且条件明确时直接 screen_by_condition；"
        "形态/技术复合条件可结合 tdx-stock-picker 与 mcp_tdx 探查，复杂或需保存时用 propose_screening。"
        "结果用 Markdown 表格展示，默认 Top 20，排除 ST，注明数据来源。"
```

- [ ] **Step 6: 运行测试**

```bash
pytest tests/llm/test_routing.py -v
```

- [ ] **Step 7: Commit**

```bash
git add vnpy_llm/routing.py vnpy_llm/prompts.py vnpy_llm/tool_result.py vnpy_ashare/ai/context.py tests/llm/test_routing.py
git commit -m "feat(llm): 选股双轨路由与 Prompt 分流"
```

---

### Task 5: 文档与 Skill 说明

**Files:**
- Modify: `skills/tdx-stock-picker/SKILL.md`
- Modify: `docs/ai-data-routing.md`
- Modify: `docs/roadmap.md`（近期可选一节）

- [ ] **Step 1: 更新 tdx-stock-picker SKILL.md**

场景 A 补充：

```markdown
若条件对应终端内置 preset（涨幅榜、换手率、低 PE 等），优先 `screen_by_condition` 直接返回。
```

场景 B 保持不变（复杂条件 → `propose_screening`）。

- [ ] **Step 2: 更新 ai-data-routing.md**

vnpy-screening 工具表改为：

```markdown
| vnpy-screening | list_screeners, screen_by_condition, propose_screening |
```

- [ ] **Step 3: roadmap 近期可选**

在「近期可选」增加一条：

```markdown
- [x] AI 对话全自动选股（内置 preset → screen_by_condition；复杂条件保留确认流程）
```

- [ ] **Step 4: Commit**

```bash
git add skills/tdx-stock-picker/SKILL.md docs/ai-data-routing.md docs/roadmap.md
git commit -m "docs: 全自动选股双轨说明与路线图"
```

---

### Task 6: 端到端验证

- [ ] **Step 1: 全量相关测试**

```bash
pytest tests/test_auto_screen.py tests/test_vnpy_screening_skill.py tests/llm/test_routing.py -v
```

Expected: 全部 PASS

- [ ] **Step 2: 手动验收清单**

1. 启动终端，确保 Redis 有行情或已配置 Tushare
2. 全屏 AI 输入：「今天涨最多的前 10 只」
   - 预期：调用 `screen_by_condition`，对话返回表格，无确认框
3. 输入：「用我的方案 xxx」
   - 预期：走 `propose_screening`，弹出确认框
4. 悬浮球同样测试一句「换手率最高的 5 只」
   - 预期：行为与全屏一致
5. 自动执行后问「解读刚才选股结果」
   - 预期：`get_screening_context` 有数据

---

## 计划自检

| 设计要求 | 对应 Task |
|----------|-----------|
| 双轨分流 | Task 1 + Task 4 |
| 统一 run_screener | Task 3 |
| 结果落库 | Task 2 + Task 3 |
| Prompt/路由 | Task 4 |
| 测试覆盖 | Task 1/3/4/6 |
| 文档 | Task 5 |
