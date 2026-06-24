"""信息流 Skill。"""

from __future__ import annotations

import json
from datetime import datetime

from vnpy_ashare.domain.feed.models import FEED_RECENT_LIMIT
from vnpy_ashare.storage.repositories import feed as feed_repo
from vnpy_skills.domain.template import SkillTemplate, ToolSpec


class VnpyFeedSkill(SkillTemplate):
    skill_name = "vnpy-feed"
    author = "zak"
    description = "查看 B 站 UP 主订阅与信息流更新（视频/动态）"

    def register_tools(self) -> list[ToolSpec]:
        return [
            ToolSpec(
                name="list_feed_subscriptions",
                description="列出当前 B 站 UP 主等信息流订阅",
                parameters={"type": "object", "properties": {}},
            ),
            ToolSpec(
                name="get_feed_items",
                description="获取信息流条目；可选触发一次同步后再读取",
                parameters={
                    "type": "object",
                    "properties": {
                        "limit": {
                            "type": "integer",
                            "description": f"条数上限，默认 {FEED_RECENT_LIMIT}，最大 50",
                        },
                        "unread_only": {"type": "boolean", "description": "仅未读，默认 false"},
                        "subscription_id": {"type": "string", "description": "按订阅 id 过滤"},
                        "refresh": {"type": "boolean", "description": "先同步 B 站再读库，默认 false"},
                    },
                },
            ),
            ToolSpec(
                name="check_bilibili_updated_today",
                description="检查订阅的 UP 主今天是否有新视频或动态（读本地库，可选 refresh 先同步）",
                parameters={
                    "type": "object",
                    "properties": {
                        "subscription_id": {"type": "string", "description": "限定某个订阅，留空为全部"},
                        "refresh": {"type": "boolean", "description": "先同步再判断，默认 false"},
                    },
                },
            ),
        ]

    def _get_feed_service(self):
        svc = self._services.get("feed")
        if svc is None:
            raise RuntimeError("FeedService 未就绪")
        return svc

    def _maybe_refresh(self, *, refresh: bool, subscription_id: str | None = None) -> str | None:
        if not refresh:
            return None
        service = self._get_feed_service()
        if subscription_id:
            result = service.sync_subscription(subscription_id)
            if result.error:
                return result.error
            return None
        job = service.sync_all_enabled()
        if not job.success and not job.skipped:
            return job.message
        return None

    def list_feed_subscriptions(self) -> str:
        service = self._get_feed_service()
        rows = []
        for sub in service.list_subscriptions():
            cursor = feed_repo.get_cursor(sub.id)
            rows.append(
                {
                    "id": sub.id,
                    "mid": sub.source_id,
                    "name": sub.display_name,
                    "enabled": sub.enabled,
                    "dynamics": sub.config.dynamics,
                    "last_ok_at": cursor.get("last_ok_at") or "",
                    "last_error": cursor.get("last_error") or "",
                }
            )
        return json.dumps({"count": len(rows), "subscriptions": rows}, ensure_ascii=False)

    def get_feed_items(
        self,
        limit: int = FEED_RECENT_LIMIT,
        unread_only: bool = False,
        subscription_id: str = "",
        refresh: bool = False,
    ) -> str:
        service = self._get_feed_service()
        sub_id = subscription_id.strip() or None
        refresh_error = self._maybe_refresh(refresh=refresh, subscription_id=sub_id)
        row_limit = max(1, min(int(limit), 50))
        items = service.list_items(
            limit=row_limit,
            unread_only=unread_only,
            subscription_id=sub_id,
        )
        payload = {
            "count": len(items),
            "refresh_error": refresh_error or "",
            "items": [_serialize_item(item) for item in items],
        }
        return json.dumps(payload, ensure_ascii=False)

    def check_bilibili_updated_today(self, subscription_id: str = "", refresh: bool = False) -> str:
        service = self._get_feed_service()
        sub_id = subscription_id.strip() or None
        refresh_error = self._maybe_refresh(refresh=refresh, subscription_id=sub_id)
        today = datetime.now().strftime("%Y-%m-%d")
        items = service.check_bilibili_updated_today(subscription_id=sub_id)
        by_author: dict[str, list[dict[str, str]]] = {}
        for item in items:
            by_author.setdefault(item.author_name, []).append(
                {
                    "title": item.title,
                    "type": item.item_type,
                    "url": item.url,
                    "published_at": item.published_at,
                }
            )
        return json.dumps(
            {
                "date": today,
                "updated": bool(items),
                "count": len(items),
                "refresh_error": refresh_error or "",
                "by_author": by_author,
            },
            ensure_ascii=False,
        )


def _serialize_item(item) -> dict[str, object]:
    return {
        "id": item.id,
        "subscription_id": item.subscription_id,
        "author_name": item.author_name,
        "item_type": item.item_type,
        "title": item.title,
        "summary": item.summary,
        "url": item.url,
        "published_at": item.published_at,
        "unread": item.is_unread,
    }
