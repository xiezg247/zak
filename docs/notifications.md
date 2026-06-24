# 消息通知（飞书）

出站走**飞书群机器人 Webhook**；应用内 toast 保留。配置：**后台 → 消息通知** 或系统配置 Tab「通知」。

---

## 配置

```env
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/...
FEISHU_WEBHOOK_SECRET=          # 可选
NOTIFY_ENABLED=true
```

| 项 | 位置 | 热加载 |
|----|------|--------|
| Webhook / 总开关 | `.env` | 即时 |
| 事件订阅、静默时段 | QSettings | 即时 |

Webhook 勿写入日志或 AI 对话。详见 [配置热加载](./config-hot-reload.md)。

---

## 事件白名单（默认多关，需勾选）

| event_id | 说明 |
|----------|------|
| `screener_intraday_done` / `screener_post_close_done` | 盘中/盘后选股完成 |
| `emotion_stage_change` | 情绪阶段变化（退潮/冰点） |
| `position_alert` | 持仓异动 |
| `radar_leader_ready` | 龙头池更新（易刷屏） |
| `scheduler_job_failed` | 定时任务失败 |
| `feed_item_new` | B 站 UP 更新 |
| `manual_test` | 设置页测试 |

限频：同事件 + dedupe_key **5 分钟** 1 条；最小间隔默认 **30 秒**。可选交易时段、午休/夜间静默。记录落库 `notify_delivery_log`。

消息默认纯文本，前缀 `【zak】`；可选 `interactive` 卡片。仅任务状态 / 规则统计 / 风险提示，不含买卖价位。

代码：`vnpy_ashare/notifications/`。联动 [风控](./risk-gate.md)、[盘中工作流](./intraday-workflow.md)、[情绪周期](./emotion-cycle.md)。

---

[飞书自定义机器人文档](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)
