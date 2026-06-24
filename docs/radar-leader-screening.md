# 雷达选龙头

人气龙头识别、连板梯队与一键选股。布局见 [雷达页](./radar-page.md)；硬过滤与 Recipe 见 [盘中选股](./intraday-screening.md)。

---

## 卡片与分层

| card_id | 标题 | 要点 |
|---------|------|------|
| `leader_pick` | 选股·龙头 | 主线龙一/龙二；`mainline` / `all_market` |
| `discovery_limit_ladder` | 发现·连板梯队 | 按 `limit_times` 分层 |
| `discovery_first_board` | 发现·首板人气 | 封板时间 + 成交额 |
| `sector_theme` | 板块·主线 | `leaders_tiered` 按板块梯队 |

| 标签 | 代号 | 说明 |
|------|------|------|
| 龙一 / 龙二 / 跟风 | `dragon_1` / `dragon_2` / `follower` | 同板块 `leader_score` 排序；每板块最多 2 龙 + 3 跟风 |
| 杂毛 | — | ST、低流动性、非主线不进池 |

10cm 主板为主；创科可标 `cm20`。`leader_score` 综合连板、封板质量、成交额分位、封板时间、主力流入、主线/共振加成。

代码：`quotes/radar/radar_leader*.py`、`screener/run/radar_leader_screen.py`。

---

## 用户路径

```text
雷达刷新 → leader_pick / 连板梯队
        → 共振侧栏或顶栏「龙头选股→Hub」
        → run_leader_screen（硬过滤 + 情绪 gate）
        → Hub 结果 / 加自选 / 导出 CSV
```

| 入口 | 说明 |
|------|------|
| 共振侧栏 | 龙头选股、龙一加自选 |
| Hub | 「雷达龙头」；历史 tag `radar_leader` |
| 板块资金 | 跳转雷达·龙头 / 龙头选股 |

冰点/退潮：空池或观察级 + 横幅。启动偏首板；高潮 mainline + 梯队；分歧仅龙一。详见 [情绪周期](./emotion-cycle.md)。

---

## 与板块资金

板块资金验证**资金流向**；雷达给**短线候选**（连板、封板、共振）。双向跳转：雷达 footer ↔ 板块详情。

---

## AI

`get_leader_pick_snapshot`、`run_leader_screen`、`explain_leader_tier`；盘后共振侧栏「盘后解读」。见 [AI 数据路由](./ai-data-routing.md)。

---

[交易体系](./trading-system.md) · [选股 Hub](./screener-hub-guide.md)
