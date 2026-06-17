# 消息通知（飞书优先）

> **阶段**：框架期需求。为 zak 提供**出站通知**能力，**优先飞书**；应用内 toast / 悬浮球提醒保留为本地通道。  
> 对齐 [盘中工作流](./intraday-workflow.md)、[风控体系](./risk-gate.md)、[情绪周期](./emotion-cycle.md)。

---

## 1. 目标与边界

### 1.1 目标

| 目标 | 说明 |
|------|------|
| **飞书优先** | 默认且主推渠道：群自定义机器人 Webhook |
| **事件驱动** | 定时任务、择时/风控、持仓异动等白名单事件 |
| **可配置** | 开关、Webhook、限频、静默时段、事件订阅 |
| **合规** | 推送为**规则/任务提醒**，不含具体买卖指令 |

### 1.2 非目标

- 不做飞书 inbound（不在飞书里下单、不读群消息做交易）
- 不替代应用内 `page_notify` / AI 悬浮球 `OrbAttention`
- 第一阶段不接飞书开放平台「应用机器人」（tenant token、卡片回调）

### 1.3 与 vnpy 内置通道关系

| 渠道 | vnpy 支持 | zak 优先级 |
|------|-----------|------------|
| **飞书 Webhook** | 无 | **P0**（新建） |
| 微信 iLink | `WechatEngine`（`MainEngine` 已注册） | P2 可选 |
| 邮件 | `EmailEngine` | P3 可选 |

zak 菜单曾**隐藏** vnpy「微信」入口；飞书走独立 `NotificationService`，不依赖 CTA/网关。

---

## 2. 飞书接入方式

### 2.1 选定方案：群自定义机器人 Webhook

```text
zak NotificationService
        │
        ▼ POST application/json
https://open.feishu.cn/open-apis/bot/v2/hook/{uuid}
```

| 项 | 说明 |
|----|------|
| 创建位置 | 飞书群 → 设置 → 群机器人 → 添加自定义机器人 |
| 鉴权 | Webhook URL 内含 secret；仅需 HTTPS POST |
| 消息类型 | Phase 1：`text`；Phase 2：`interactive` 卡片（可选） |
| 频率 | 飞书侧约 **100 次/分钟/机器人**；zak 侧另设合并限频 |

### 2.2 消息体（Phase 1）

**纯文本**（实现简单、移动端可读）：

```json
{
  "msg_type": "text",
  "content": {
    "text": "【zak】盘中选股完成\n命中 18 条 · intraday_multi\n2026-06-17 10:02"
  }
}
```

**签名验证**（若机器人开启「签名校验」）：

```text
timestamp + "\n" + secret  → HmacSHA256 → Base64
```

请求头：

```text
Content-Type: application/json
（可选）X-Lark-Signature: ...
（可选）X-Lark-Request-Timestamp: ...
```

Phase 1 建议：配置页说明「可先关闭签名校验」；Phase 2 支持 `FEISHU_WEBHOOK_SECRET` 自动签名。

### 2.3 安全存储

| 配置 | 位置 | 说明 |
|------|------|------|
| `FEISHU_WEBHOOK_URL` | `.env` | 完整 Webhook URL，**敏感** |
| `FEISHU_WEBHOOK_SECRET` | `.env` | 签名校验 secret，可选 |
| `NOTIFY_ENABLED` | `.env` 或 QSettings | 总开关 |
| 事件订阅 | QSettings `notify/events/*` | 按事件类型开关 |

禁止写入日志、commit、AI 上下文明文 URL。

---

## 3. 架构

```text
业务触发点（scheduler / emotion / risk / position）
        │
        ▼
NotificationService.notify(event: NotifyEvent)
        │
        ├─► 规则：enabled? 订阅? 静默时段? 去重/合并?
        │
        ▼
NotifyDispatcher（后台 Queue + Worker 线程）
        │
        ├─► FeishuWebhookChannel.send(text)     ← 优先
        ├─► VnpyWechatChannel（可选）
        └─► EmailChannel（可选）
        │
        ▼
落库 notify_delivery_log（可选，Phase 2）
```

### 3.1 模块结构（规划）

```text
packages/vnpy-ashare/vnpy_ashare/notifications/
├── __init__.py
├── models.py              # NotifyEvent, NotifyResult, DeliveryStatus
├── service.py             # NotificationService.notify / test_send
├── dispatcher.py          # 队列、Worker、限频
├── rules.py               # 订阅、静默、dedupe key
├── channels/
│   ├── base.py
│   ├── feishu_webhook.py
│   ├── vnpy_wechat.py     # 委托 MainEngine WechatEngine
│   └── email.py
└── formatters.py          # 各 event 标题/正文模板
```

| 模块 | 路径 | 职责 |
|------|------|------|
| 配置 | `config/schema` + `.env` | Webhook URL、secret |
| UI | `ui/shell/settings/notify_section.py` | 绑定、测试、事件勾选 |
| 启动 | `app/engine.py` 或 `AshareEngine` | 注册 `NotificationService` |

---

## 4. 事件白名单

仅**白名单**事件可出站；默认关闭，用户在设置中逐项开启。

| event_id | 标题 | 触发源 | 默认 | 说明 |
|----------|------|--------|------|------|
| `screener_intraday_done` | 盘中选股完成 | `scheduler` `screen_intraday` | **开** | 替代仅 Orb 提醒 |
| `screener_post_close_done` | 盘后选股完成 | `screen_post_close` | 关 | |
| `emotion_stage_change` | 情绪阶段变化 | `emotion_cycle` | **开** | 尤其 → 退潮/冰点 |
| `risk_gate_change` | 风控状态变化 | `risk_gate` | **开** | caution / halt |
| `position_alert` | 持仓异动 | `position_anomaly` | 关 | 浮亏≤−5%、卖出信号等 |
| `journal_violation` | 流水违规 | `trade_journal` | 关 | off_plan / 退潮买入 / 亏损加仓 / 浮亏扛单 |
| `radar_leader_ready` | 龙头池更新 | 雷达 `leader_pick` | 关 | 易刷屏，需高阈值 |
| `scheduler_job_failed` | 定时任务失败 | `TaskSchedulerManager` | **开** | |
| `manual_test` | 测试消息 | 设置页按钮 | — | |

### 4.1 去重与合并

| 规则 | 参数 |
|------|------|
| 同 event + 同 dedupe_key | 5 分钟内只发 1 条 |
| `position_alert` | dedupe_key = vt_symbol + reason |
| `emotion_stage_change` | dedupe_key = stage |
| 队列合并 | Worker 每 10s 批量合并同类型（Phase 2） |

### 4.2 静默时段

| 项 | 默认 |
|----|------|
| 非交易时段 | 可选「仅交易时段推送」 |
| 午休 | 11:35–13:00 不推 `position_alert` |
| 夜间 | 22:00–08:00 仅 `scheduler_job_failed` |

配置：`QSettings notify/quiet_hours`。

---

## 5. 消息模板

统一前缀 `【zak】`；正文简体中文；**禁止**「建议买入/卖出 X 价」。

### 5.1 示例

**盘中选股完成**

```text
【zak】盘中选股完成
配方 intraday_multi · 命中 18 条
时间 2026-06-17 10:02:15
打开客户端查看选股 Hub 运行历史
```

**情绪退潮**

```text
【zak】情绪阶段 → 退潮
涨停 42 · 跌停 28 · 最高连板 4→2
建议：不开新仓（规则参考，非投资建议）
```

**风控熔断**

```text
【zak】风控状态 → 熔断(halt)
当日浮亏合计 -3.2% · 周回撤 5.1%
请复盘后再操作
```

**持仓异动**

```text
【zak】持仓提醒
贵州茅台 600519 · 浮盈 -5.2% · 标签：浮亏
退出信号：卖出 · T+1：可卖
```

### 5.2 Phase 2 卡片（可选）

飞书 `msg_type: interactive` 展示「打开 zak」按钮（自定义 URL scheme 或仅文案提示）。

---

## 6. 触发点改造

### 6.1 已有逻辑 → 通知

| 现状 | 改造 |
|------|------|
| `_handle_scheduler_job` 仅 Orb + 选股页 | 成功时 `notify(screener_*_done)` |
| `page_notify` 全局 | **不**全部转发 |
| 无 emotion / risk | 引擎状态变更时 notify |

### 6.2 调用约定

```python
# 规划 API
service.notify(
    "screener_intraday_done",
    dedupe_key="screen_intraday",
    payload={"hit_count": 18, "recipe": "intraday_multi", "message": "..."},
)
```

Worker 内 HTTP 失败：重试 2 次（指数退避）；仍失败写 `last_error` 供设置页展示。

---

## 7. UI 与配置

### 7.1 入口

| 入口 | 说明 |
|------|------|
| 菜单 **后台 → 消息通知…** | 或 配置页 Tab「通知」 |
| 测试按钮 | 「发送飞书测试消息」→ `manual_test` |

### 7.2 设置项

| 项 | 控件 |
|----|------|
| 启用通知 | 总开关 |
| 飞书 Webhook URL | 密码框 + 帮助链接 |
| 签名校验 Secret | 可选密码框 |
| 最小发送间隔 | 秒，默认 30（低于 vnpy 微信 60s） |
| 事件订阅 | 多选 checklist（§4 表） |
| 静默时段 | 可选 |
| 次要渠道 | 微信/邮件（折叠，P2） |

保存：`FEISHU_*` 写 `.env`；订阅写 QSettings；Webhook 变更后自动 `test_send`。

### 7.3 与 config-hot-reload

| 配置 | 档位 |
|------|------|
| `FEISHU_WEBHOOK_URL` / `SECRET` | **即时** | `load_dotenv` + `NotificationService.reload()` |
| `NOTIFY_ENABLED` | **即时** |
| 事件订阅 QSettings | **即时** |

---

## 8. 依赖与网络

| 项 | 说明 |
|----|------|
| HTTP 库 | 复用 `requests`（vnpy 已依赖） |
| 出站 | 需能访问 `open.feishu.cn` |
| 代理 | 遵循系统/`HTTPS_PROXY` |
| 离线 | 队列暂存 ≤50 条，恢复后发送；超限丢弃并 log |

---

## 9. 测试

| 文件 | 覆盖 |
|------|------|
| `tests/ashare/notifications/test_feishu_webhook.py` | 签名、payload、HTTP mock |
| `tests/ashare/notifications/test_rules.py` | 去重、静默、订阅 |
| `tests/ashare/notifications/test_dispatcher.py` | 队列、限频 |

手动：设置页「测试消息」+ 关闭签名校验的测试群机器人。

---

## 10. 实施分期

### Phase 1 — 飞书 MVP

- [x] `FeishuWebhookChannel` + `NotificationService` + Worker
- [x] `.env` + 设置页 Tab「通知」（URL、总开关、测试）
- [x] 事件：`screener_intraday_done`、`scheduler_job_failed`、`manual_test`
- [x] 接入 scheduler `job_finished_hook`

### Phase 2 — 短线体系联动

- [x] `emotion_stage_change`、`risk_gate_change`
- [x] `position_alert`（去重）
- [x] 签名校验、delivery log

### Phase 3 — 扩展

- [ ] 飞书 interactive 卡片
- [ ] 可选 `VnpyWechatChannel` / Email
- [ ] `radar_leader_ready`（高阈值）

---

## 11. 合规

- 推送内容 = 任务状态 / 规则统计 / 风险提示，**不构成**投资建议。
- 模板末尾可选固定句：「规则计算结果，仅供研究。」
- Webhook URL 不得出现在 AI 对话、导出文件、截图教程明文。

---

## 参考

- [飞书自定义机器人文档](https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot)
- [盘中工作流](./intraday-workflow.md)
- [风控体系](./risk-gate.md)
- [情绪周期引擎](./emotion-cycle.md)
- [配置分级热加载](./config-hot-reload.md)
