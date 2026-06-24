# 信息流

聚合外部订阅源时间线，当前支持 **B 站 UP 主动态**；侧栏 `Ctrl+Shift+F` 进入，不承担选股/看盘主路径。

---

## 1. 页面结构

| 区域 | 说明 |
|------|------|
| 订阅源（左） | 已订阅 UP 列表、添加/删除、按源筛选时间线 |
| 时间线（右） | 动态卡片流；点击可在浏览器打开原文 |
| 工具栏 | 「立即同步」手动拉取 |

实现：`ui/features/info_feed/`（`page.py`、`subscription_panel.py`、`timeline_view.py`）。

---

## 2. B 站订阅

### 2.1 前置配置

在 `.env` 配置 `BILIBILI_COOKIES`（登录态 Cookie 字符串）。未配置时页面提示，无法搜索/添加 UP。

### 2.2 添加订阅

1. 点击「添加 UP 主」
2. 按 **mid** 或 **关键词搜索** 定位 UP
3. 可选「添加后立即同步」

单用户订阅上限见 `MAX_FEED_SUBSCRIPTIONS`（`domain/feed/models.py`）。

### 2.3 同步策略

| 触发 | 行为 |
|------|------|
| 定时任务 `sync_bilibili_feed` | 默认启用；间隔 300s；仅在 **08:00–20:00** 执行（`sync_bilibili.py`） |
| 页面「立即同步」 | 忽略时间窗，`force=True` |
| 新订阅 | 可选 `sync_now` 立即拉首屏 |

同步逻辑：`services/feed.py` → B 站 API → `feed_items` 去重写入。

### 2.4 通知

新动态可触发 `feed_item_new` 事件，经 [消息通知](./notifications.md) 出站（**默认关闭**，需在系统配置 → 通知事件白名单启用）。

---

## 3. 数据存储

App DB（`zak.db`）表：

| 表 | 用途 |
|----|------|
| `feed_subscriptions` | 订阅源（类型、source_id、展示名、启用状态） |
| `feed_items` | 归一化后的动态条目 |
| `feed_cursors` | 各订阅同步游标与最近错误 |

Repository：`storage/repositories/feed.py`。

---

## 4. AI 上下文

打开信息流页时，`ai/context/feed.py` 将近期条目摘要写入 `context_store`，供悬浮球/全屏对话引用（只读，不自动发送）。

---

## 参考

- [产品说明 § 左侧导航](./product-plan.md#左侧导航)
- [数据设计](./data-design.md)
- [消息通知](./notifications.md)
