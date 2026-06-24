# 信息流

`Ctrl+Shift+F`。B 站 UP 主动态时间线；非选股/看盘主路径。

左栏订阅源管理，右栏动态卡片（点击浏览器打开原文）；工具栏「立即同步」。

## B 站

`.env` 配置 `BILIBILI_COOKIES`（未配置则无法搜索/添加）。添加 UP：mid 或关键词；上限 `MAX_FEED_SUBSCRIPTIONS`。

| 触发 | 行为 |
|------|------|
| `sync_bilibili_feed` | 默认 300s；**08:00–20:00** |
| 页面立即同步 | `force=True` 忽略时间窗 |

`services/feed.py` → `feed_subscriptions` / `feed_items` / `feed_cursors`（见 [数据设计](./data-design.md)）。新动态可推 `feed_item_new`（默认关，见 [通知](./notifications.md)）。

打开页时 `ai/context/feed.py` 写入 `context_store` 供 AI 只读引用。

---

[产品说明](./product-plan.md) · [架构说明](./architecture.md)
