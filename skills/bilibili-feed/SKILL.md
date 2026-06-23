---
name: bilibili-feed
description: 查看 B 站 UP 主订阅与信息流。触发词：B站、UP主、信息流、今天更新、最新动态、最新视频
---

# B 站信息流

系统已内置 `vnpy-feed` Python Skill，优先调用以下工具（**不要** subprocess 调外部脚本）：

| 工具 | 用途 |
|------|------|
| `list_feed_subscriptions` | 当前订阅的 UP 主 |
| `get_feed_items` | 最近条目；`refresh=true` 先同步 |
| `check_bilibili_updated_today` | 今天是否有更新 |

用户需在 zak 配置 `BILIBILI_COOKIES`；未配置时说明无法拉取新数据，但仍可读本地库。
