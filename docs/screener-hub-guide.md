# 选股 Hub 使用指南

`Ctrl+7`：「条件选股」+「多因子配方」双 Tab，共用硬过滤与结果区。技术说明见 [盘中选股](./intraday-screening.md)。

---

## 条件选股

1. 左栏选 preset 或自定义涨幅/换手
2. 展开 **硬过滤**（模板：保守/均衡/激进）
3. **运行条件选股** → 右侧结果、行业分布、diff

**快捷入口**（左栏，默认折叠）：形态选股、雷达共振、**雷达龙头**、行业成分。雷达类需先在 [雷达页](./radar-page.md) 刷新。

## 多因子配方

1. 选内置 `intraday_multi`、`ultra_short_unified` 等或自配维度权重
2. **运行配方** → 左侧收件箱；可按 `[盘中]` / `[盘后]` 过滤

交易时段顶栏显示 Redis/Tushare 数据状态，可 **刷新行情**。

## 结果操作

| 按钮 | 说明 |
|------|------|
| 加入自选 / 下载日 K | 批量写入自选（≤50）或补 K 线 |
| 策略回测 / 批量回测 | 单票或多只 → 回测对比 |
| 找同类 | 标杆对标 |
| **短线主池** | 激进硬过滤 + 连板/龙头分收窄 |
| 导出 CSV | 按结果类型自动选列 |

硬过滤规则、模板与 `RECIPE_*` 覆盖见 [盘中选股 §3](./intraday-screening.md#3-硬过滤)。退潮建议保守模板或暂停选股。

## AI 对话（`Ctrl+L`）

面板上方 **快捷 chip** 与左栏入口对齐（详见 [AI 数据路由 §快捷指令](./ai-data-routing.md#快捷指令ctrll-面板)）：

| chip | 说明 |
|------|------|
| 解读选股结果 | 有最近结果时出现；`explain_screening_run` |
| 雷达龙头 | `run_leader_screen`（须先刷新雷达） |
| 共振解读 | `get_radar_snapshot` |
| 形态选股 | 老鸭头 / 均线多头 / W 底 / 主题投资 |
| 条件选股 | 盘中多因子 · 盘后多因子 · 低 PE · 主力净流入 · 成交量放大 |

自然语言仍可用下表；`propose_screening` / `propose_recipe` 执行前弹窗确认。

| 你说 | 工具 |
|------|------|
| 盘中强势股 / 多因子 | `run_recipe` |
| 涨幅榜 / 低 PE | `screen_by_condition` |
| 老鸭头 / W 底 | `screen_by_pattern` |
| 解读结果 / 能不能做 / 龙头池 | `get_screening_context` / `get_emotion_cycle` / `run_leader_screen` |

路由见 [AI 数据路由](./ai-data-routing.md)。

## 常见问题

| 现象 | 处理 |
|------|------|
| 交易时段无结果 | 跑「行情采集」或开市场页预热 Redis |
| 财务 preset 失败 | 配置 `TUSHARE_TOKEN` |
| 批量回测无数据 | 先下载日 K |
| 雷达龙头空 | 刷新「选股·龙头」卡；退潮 gate 可能为空 |

---

[雷达选龙头](./radar-leader-screening.md) · [功能索引](./feature-index.md) · [产品说明](./product-plan.md)
