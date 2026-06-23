"""信息流页 AI 上下文。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vnpy_ashare.app.engine_access import get_feed_service
from vnpy_ashare.ai.context.store import set_ai_context
from vnpy_ashare.domain.feed.models import FEED_RECENT_LIMIT
from vnpy_common.ai.protocol import AiContextData, QuickAction

if TYPE_CHECKING:
    from vnpy_ashare.services.feed import FeedService
    from vnpy_ashare.domain.feed.models import FeedItem


def sync_info_feed_context(main_engine=None) -> None:
    from vnpy_ashare.ai.context.enrichment import enrich_context_with_actions

    service = get_feed_service(main_engine)
    extra = format_feed_page_extra(service)
    set_ai_context(enrich_context_with_actions(AiContextData(page="信息流", extra=extra)))


def format_feed_page_extra(service: FeedService | None) -> str:
    if service is None:
        return "【信息流】服务未就绪。"
    unread = service.count_unread()
    subs = service.list_subscriptions()
    enabled = sum(1 for row in subs if row.enabled)
    lines = [f"【信息流】订阅 {len(subs)} 个（启用 {enabled}）· 未读 {unread}"]
    if subs:
        names = "、".join(sub.display_name or sub.source_id for sub in subs[:8])
        if len(subs) > 8:
            names += f" 等 {len(subs)} 个"
        lines.append(f"订阅：{names}")
    recent = service.list_items(limit=FEED_RECENT_LIMIT, unread_only=True)
    if recent:
        lines.append("未读摘要：")
        for item in recent:
            line = f"- {item.author_name} · [{_type_label(item.item_type)}] {item.title}"
            summary = (item.summary or "").strip()
            if summary and summary != (item.title or "").strip():
                line += f"\n  {summary}"
            lines.append(line)
    elif service.list_items(limit=FEED_RECENT_LIMIT):
        lines.append("暂无未读；最近条目可查 get_feed_items。")
    else:
        lines.append("尚无条目；配置 Cookie 后添加 UP 主并同步。")
    return "\n".join(lines)


def build_feed_page_quick_actions() -> list[QuickAction]:
    return [
        QuickAction(
            id="feed_today",
            label="今天更新了吗",
            auto_send=True,
            prompt=(
                "请调用 check_bilibili_updated_today（必要时 refresh=true）"
                "回答：我订阅的 B 站 UP 主今天是否有新视频或动态，并列出标题与链接。"
            ),
        ),
        QuickAction(
            id="feed_unread",
            label="摘要未读",
            auto_send=True,
            prompt=(
                "请调用 get_feed_items，unread_only=true，limit=5，"
                "用简短条目列表概括未读信息流，不要编造。"
            ),
        ),
    ]


def build_ask_ai_prompt_for_feed_item(item: FeedItem) -> str:
    type_label = _type_label(item.item_type)
    return (
        f"请解读这条 B 站更新：UP 主「{item.author_name}」，类型 {type_label}，"
        f"标题「{item.title}」。\n"
        f"链接：{item.url}\n"
        f"摘要：{item.summary or '（无）'}\n"
        "可先调用 get_feed_items 核对上下文；仅基于已知信息简要点评，不要编造。"
    )


def _type_label(item_type: str) -> str:
    return {"video": "视频", "dynamic": "动态", "article": "专栏"}.get(item_type, item_type)
