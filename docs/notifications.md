# 消息通知（飞书）

> 出站通知走**飞书群机器人 Webhook**；应用内 toast 保留。详见 [风控](./risk-gate.md)、[盘中工作流](./intraday-workflow.md)。

---

## 1. 配置

### 飞书机器人

1. 飞书群 → 设置 → 群机器人 → 添加**自定义机器人**
2. 复制 Webhook URL 写入 `.env`：

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/...
FEISHU_WEBHOOK_SECRET=          # 可选，签名校验
NOTIFY_ENABLED=true
```

3. 菜单 **后台 → 消息通知**（或系统配置 Tab「通知」）→ 勾选事件 → **发送测试消息**

| 配置 | 位置 | 热加载 |
|------|------|--------|
| Webhook URL / Secret | `.env` | 即时 |
| 总开关 | `.env` 或 QSettings | 即时 |
| 事件订阅、静默时段 | QSettings | 即时 |

Webhook 勿写入日志或 AI 对话。

---

## 2. 事件白名单

默认关闭，需逐项开启：

| event_id | 说明 | 默认 |
|----------|------|------|
| `screener_intraday_done` | 盘中选股完成 | 开 |
| `screener_post_close_done` | 盘后选股完成 | 关 |
| `emotion_stage_change` | 情绪阶段变化（尤其退潮/冰点） | 开 |
| `position_alert` | 持仓异动（浮亏、卖出信号等） | 关 |
| `radar_leader_ready` | 龙头池更新（易刷屏） | 关 |
| `scheduler_job_failed` | 定时任务失败 | 开 |
| `feed_item_new` | B 站 UP 更新 | 关 |
| `manual_test` | 设置页测试 | — |

### 限频与静默

- 同事件 + 同 dedupe_key：**5 分钟**内只发 1 条
- 最小发送间隔：默认 **30 秒**
- 可选：仅交易时段、午休 11:35–13:00 不推持仓、夜间 22:00–08:00 仅任务失败

发送记录落库 `notify_delivery_log`。

---

## 3. 消息格式

默认纯文本，前缀 `【zak】`；可选 `interactive` 卡片（`NOTIFY_OPEN_URL` 可配打开链接）。

示例：

```text
【zak】情绪阶段 → 退潮
涨停 42 · 跌停 28 · 最高连板 4→2
建议：不开新仓（规则参考，非投资建议）
```

**合规**：仅任务状态 / 规则统计 / 风险提示，不含具体买卖价位。

---

## 4. 架构（简）

```text
scheduler / emotion_cycle / position_anomaly / feed
        → NotificationService.notify()
        → 规则（订阅、去重、静默）
        → FeishuWebhookChannel POST
```

代码：`vnpy_ashare/notifications/`。

---

## 参考

[飞书自定义机器人文档](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot) · [配置热加载](./config-hot-reload.md) · [情绪周期](./emotion-cycle.md)
