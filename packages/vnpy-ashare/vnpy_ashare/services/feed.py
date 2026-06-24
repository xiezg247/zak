"""信息流 Service。"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from vnpy_ashare.domain.feed.models import (
    FEED_RECENT_LIMIT,
    MAX_FEED_SUBSCRIPTIONS,
    SOURCE_TYPE_BILIBILI_UP,
    FeedItem,
    FeedItemDraft,
    FeedSubscription,
    FeedSubscriptionConfig,
    SyncResult,
)
from vnpy_ashare.integrations.bilibili.client import BilibiliApiError, BilibiliClient
from vnpy_ashare.integrations.bilibili.dynamics import (
    get_dynamic_detail,
    list_recent_dynamics,
    sleep_before_detail_fetch,
)
from vnpy_ashare.integrations.bilibili.normalize import (
    dynamic_needs_detail_fetch,
    merge_dynamic_drafts,
    normalize_dynamic,
)
from vnpy_ashare.integrations.bilibili.user import get_user_profile, search_users
from vnpy_ashare.jobs.core.result import JobResult
from vnpy_ashare.notifications.core.events import NOTIFY_EVENT_FEED_ITEM_NEW
from vnpy_ashare.services.base import BaseService
from vnpy_ashare.storage.repositories import feed as feed_repo

if TYPE_CHECKING:
    from vnpy_ashare.app.engine import AshareEngine

_SUBSCRIPTION_SLEEP_SEC = 3.0
_MAX_DETAIL_FETCH_PER_SYNC = 20


class FeedService(BaseService):
    def __init__(self, engine: AshareEngine) -> None:
        super().__init__(engine)
        self._client_factory: Callable[[], BilibiliClient] = BilibiliClient

    def set_client_factory(self, factory: Callable[[], BilibiliClient]) -> None:
        self._client_factory = factory

    def cookies_configured(self) -> bool:
        return self._client_factory().cookies_configured

    def list_subscriptions(self) -> list[FeedSubscription]:
        return feed_repo.list_subscriptions()

    def search_bilibili_users(self, keyword: str, *, limit: int = 8) -> list[dict[str, str]]:
        client = self._client_factory()
        if not client.cookies_configured:
            raise RuntimeError("未配置 BILIBILI_COOKIES")
        return search_users(client, keyword, limit=limit)

    def add_bilibili_up(
        self,
        *,
        mid: str | None = None,
        keyword: str | None = None,
        display_name: str | None = None,
        avatar_url: str | None = None,
        config: FeedSubscriptionConfig | None = None,
        sync_now: bool = True,
    ) -> FeedSubscription:
        if feed_repo.count_subscriptions() >= MAX_FEED_SUBSCRIPTIONS:
            raise RuntimeError(f"订阅数量已达上限（{MAX_FEED_SUBSCRIPTIONS}）")

        client = self._client_factory()
        if not client.cookies_configured:
            raise RuntimeError("未配置 BILIBILI_COOKIES")

        resolved_mid = (mid or "").strip()
        resolved_name = (display_name or "").strip()
        resolved_avatar = (avatar_url or "").strip()
        if not resolved_mid:
            query = (keyword or "").strip()
            if not query:
                raise ValueError("请提供 mid 或搜索关键词")
            matches = search_users(client, query, limit=1)
            if not matches:
                raise RuntimeError(f"未找到 UP 主：{query}")
            resolved_mid = str(matches[0]["mid"])
            resolved_name = str(matches[0].get("name") or "")
            resolved_avatar = str(matches[0].get("avatar") or "")

        existing = feed_repo.find_subscription_by_source(SOURCE_TYPE_BILIBILI_UP, resolved_mid)
        if existing is not None:
            raise RuntimeError(f"已订阅：{existing.display_name or existing.source_id}")

        if not resolved_name or not resolved_avatar:
            try:
                profile = get_user_profile(client, resolved_mid)
            except BilibiliApiError:
                profile = {"name": "", "avatar": ""}
            resolved_name = resolved_name or profile["name"] or resolved_mid
            resolved_avatar = resolved_avatar or profile["avatar"]

        subscription = feed_repo.insert_subscription(
            source_type=SOURCE_TYPE_BILIBILI_UP,
            source_id=resolved_mid,
            display_name=resolved_name,
            avatar_url=resolved_avatar,
            config=config,
        )
        if sync_now:
            result = sync_subscription_record(subscription.id, client)
            if result.error:
                raise RuntimeError(result.error)
            subscription = feed_repo.get_subscription(subscription.id) or subscription
        return subscription

    def update_subscription(
        self,
        subscription_id: str,
        *,
        enabled: bool | None = None,
        config: FeedSubscriptionConfig | None = None,
    ) -> None:
        feed_repo.update_subscription(subscription_id, enabled=enabled, config=config)

    def remove_subscription(self, subscription_id: str) -> None:
        feed_repo.delete_subscription(subscription_id)

    def list_items(
        self,
        *,
        limit: int = FEED_RECENT_LIMIT,
        unread_only: bool = False,
        subscription_id: str | None = None,
    ) -> list[FeedItem]:
        return feed_repo.list_items(
            limit=limit,
            unread_only=unread_only,
            subscription_id=subscription_id,
        )

    def count_unread(self, *, subscription_id: str | None = None) -> int:
        return feed_repo.count_unread(subscription_id=subscription_id)

    def mark_read(self, item_ids: list[str]) -> None:
        feed_repo.mark_read(item_ids)

    def mark_all_read(self, *, subscription_id: str | None = None) -> None:
        feed_repo.mark_all_read(subscription_id=subscription_id)

    def mark_unread(self, item_ids: list[str]) -> None:
        feed_repo.mark_unread(item_ids)

    def check_bilibili_updated_today(self, *, subscription_id: str | None = None) -> list[FeedItem]:
        today = datetime.now().strftime("%Y-%m-%d")
        return feed_repo.list_items_published_on(today, subscription_id=subscription_id)

    def sync_subscription(self, subscription_id: str) -> SyncResult:
        result = sync_subscription_record(subscription_id, self._client_factory())
        if result.inserted:
            self._emit_new_items(result.inserted)
        return result

    def sync_all_enabled(self) -> JobResult:
        return run_feed_sync(
            sync_one=lambda sub_id: self.sync_subscription(sub_id),
            purge=feed_repo.purge_old_items,
            cookies_configured=self.cookies_configured(),
        )

    def _emit_new_items(self, items: list[FeedItem]) -> None:
        if not items:
            return
        notification = getattr(self.engine, "notification_service", None)
        if notification is None:
            return
        for item in items:
            notification.notify(
                NOTIFY_EVENT_FEED_ITEM_NEW,
                dedupe_key=f"{item.source_type}:{item.external_id}",
                payload={
                    "author_name": item.author_name,
                    "title": item.title,
                    "url": item.url,
                    "item_type": item.item_type,
                },
            )


def sync_subscription_record(subscription_id: str, client: BilibiliClient) -> SyncResult:
    subscription = feed_repo.get_subscription(subscription_id)
    if subscription is None:
        return SyncResult(subscription_id=subscription_id, error="订阅不存在")
    if not subscription.enabled:
        return SyncResult(subscription_id=subscription_id, error="订阅已禁用")
    if not client.cookies_configured:
        feed_repo.update_cursor(subscription_id, last_error="未配置 BILIBILI_COOKIES")
        return SyncResult(subscription_id=subscription_id, error="未配置 BILIBILI_COOKIES")

    cursor = feed_repo.get_cursor(subscription_id)
    max_dynamic_id = str(cursor["last_dynamic_id"])
    inserted: list[FeedItem] = []

    try:
        if subscription.config.dynamics:
            dynamic_drafts: list[FeedItemDraft] = []
            detail_fetches = 0
            for raw in list_recent_dynamics(client, subscription.source_id, count=FEED_RECENT_LIMIT):
                draft = normalize_dynamic(raw, author_name=subscription.display_name)
                if draft is None:
                    continue
                if dynamic_needs_detail_fetch(draft) and detail_fetches < _MAX_DETAIL_FETCH_PER_SYNC:
                    detail_fetches += 1
                    sleep_before_detail_fetch()
                    detail_raw = get_dynamic_detail(client, draft.external_id)
                    if detail_raw is not None:
                        detail_draft = normalize_dynamic(detail_raw, author_name=subscription.display_name)
                        if detail_draft is not None:
                            draft = merge_dynamic_drafts(draft, detail_draft)
                dynamic_drafts.append(draft)
                dynamic_id = draft.external_id
                if dynamic_id.isdigit() and (not max_dynamic_id.isdigit() or int(dynamic_id) > int(max_dynamic_id)):
                    max_dynamic_id = dynamic_id
                elif not max_dynamic_id:
                    max_dynamic_id = dynamic_id
            inserted.extend(
                feed_repo.upsert_items(
                    subscription.id,
                    subscription.source_type,
                    dynamic_drafts,
                )
            )

        feed_repo.update_cursor(
            subscription.id,
            last_dynamic_id=max_dynamic_id,
            last_ok_at=datetime.now().isoformat(timespec="seconds"),
            last_error="",
        )
        return SyncResult(subscription_id=subscription.id, new_items=len(inserted), inserted=inserted)
    except BilibiliApiError as ex:
        feed_repo.update_cursor(subscription.id, last_error=str(ex))
        return SyncResult(subscription_id=subscription.id, error=str(ex))


def run_feed_sync(
    *,
    sync_one: Callable[[str], SyncResult] | None = None,
    purge: Callable[[], int] | None = None,
    cookies_configured: bool | None = None,
) -> JobResult:
    configured = cookies_configured if cookies_configured is not None else BilibiliClient().cookies_configured
    if not configured:
        return JobResult(success=True, skipped=True, message="未配置 BILIBILI_COOKIES，已跳过 B 站订阅同步")

    subscriptions = feed_repo.list_subscriptions(enabled_only=True)
    if not subscriptions:
        return JobResult(success=True, skipped=True, message="无启用的信息流订阅，已跳过")

    sync_fn = sync_one or (lambda sub_id: sync_subscription_record(sub_id, BilibiliClient()))
    total_new = 0
    errors: list[str] = []
    for index, subscription in enumerate(subscriptions):
        result = sync_fn(subscription.id)
        total_new += result.new_items
        if result.error:
            label = subscription.display_name or subscription.source_id
            errors.append(f"{label}: {result.error}")
        if index < len(subscriptions) - 1:
            time.sleep(_SUBSCRIPTION_SLEEP_SEC)

    purged = purge() if purge is not None else feed_repo.purge_old_items()
    if errors and total_new == 0:
        return JobResult(success=False, message="；".join(errors[:3]))
    message = f"同步完成：新增 {total_new} 条"
    if purged:
        message += f"，清理 {purged} 条过期"
    if errors:
        message += f"；部分失败 {len(errors)} 个"
    return JobResult(success=True, message=message)
