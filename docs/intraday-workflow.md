# 盘中工作流（短线为主）

把 [交易体系](./trading-system.md) 串成 **盘前 → 盘中 → 盘后**。自选页布局预设默认「盘中」；信号区默认 Profile `short_swing`。

---

## 总流程

```text
盘前：守则(Ctrl+1) → 情绪预期 → 次日计划(3–5只) → 补日 K
盘中：择时闸 → 选股/信号区 → 登记持仓 → 风控异动
盘后：笔记复盘 → 更新计划 → 导出/飞书
```

| 阶段 | 重点页面 |
|------|----------|
| 极致短线 1–3 日 | 雷达、市场、自选持仓；LimitBoard、OvernightExit |
| 短线波段 3–10 日 | 雷达展望、信号区 `AshareShortBreakoutStrategy` |
| 中线 2–8 周 | 回测、团队分析 `AshareDoubleMaStrategy` |

---

## 逐步

**盘前**： [守则](./trading-system.md#13-守则-playbook默认首屏) Playbook → [市场](./market-page.md)/[雷达](./radar-page.md) 看环境 → 交易计划对话框 → `propose_trading_plan`（AI）。

**盘中**：情绪芯片 → [雷达选龙头](./radar-leader-screening.md) → [信号区](./watchlist.md#4-信号区) ≤10 → [持仓区](./watchlist.md#5-持仓区) 登记 → [风控/通知](./risk-gate.md)。池子上限：计划 3–5 · 信号 10 · 自选 50。

**盘后**：笔记 + Playbook；CSV 导出；雷达「盘后解读」。

### 按情绪阶段

| 阶段 | 做 | 少做 |
|------|-----|------|
| 冰点 | 空仓试错 | 打板追高 |
| 启动 | 首板二板 | 重仓龙头 |
| 高潮 | 龙头+共振 | 杂毛 |
| 分歧 | 龙一低吸减仓 | 跟风 |
| 退潮 | 隔日卖、不新开 | 一切买入 |

快捷：雷达 → Hub · 选股 → 自选 · 自选 → 信号/持仓 · `Ctrl+L` AI。

---

[功能索引](./feature-index.md) · [策略 Profile](./strategy-profiles.md)
