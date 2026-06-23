"""信息流订阅与条目模型。"""

from __future__ import annotations

from typing import Any

from pydantic import Field

from vnpy_common.domain.base import FrozenModel, MutableModel

SOURCE_TYPE_BILIBILI_UP = "bilibili_up"
MAX_FEED_SUBSCRIPTIONS = 50
FEED_RETENTION_DAYS = 90
FEED_RECENT_LIMIT = 5


class FeedSubscriptionConfig(MutableModel):
    videos: bool = Field(default=True, description="采集投稿视频")
    dynamics: bool = Field(default=True, description="采集空间动态")


class FeedSubscription(FrozenModel):
    id: str = Field(description="订阅 id")
    source_type: str = Field(description="来源类型")
    source_id: str = Field(description="来源标识，如 B 站 mid")
    display_name: str = Field(description="展示名称")
    avatar_url: str = Field(default="", description="头像 URL")
    config: FeedSubscriptionConfig = Field(description="采集配置")
    enabled: bool = Field(default=True, description="是否启用")
    sort_order: int = Field(default=0, description="排序")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


class FeedItemDraft(MutableModel):
    external_id: str = Field(description="来源侧唯一 id")
    item_type: str = Field(description="video | dynamic | article")
    title: str = Field(default="", description="标题")
    summary: str = Field(default="", description="摘要")
    url: str = Field(description="链接")
    author_name: str = Field(default="", description="作者名")
    published_at: str = Field(description="发布时间 ISO")
    payload: dict[str, Any] = Field(default_factory=dict, description="扩展字段")


class FeedItem(FrozenModel):
    id: str = Field(description="条目 id")
    subscription_id: str = Field(description="订阅 id")
    source_type: str = Field(description="来源类型")
    external_id: str = Field(description="来源侧唯一 id")
    item_type: str = Field(description="条目类型")
    title: str = Field(description="标题")
    summary: str = Field(description="摘要")
    url: str = Field(description="链接")
    author_name: str = Field(description="作者名")
    published_at: str = Field(description="发布时间")
    payload: dict[str, Any] = Field(default_factory=dict, description="扩展字段")
    read_at: str | None = Field(default=None, description="已读时间")
    created_at: str = Field(description="入库时间")

    @property
    def is_unread(self) -> bool:
        return self.read_at is None


class SyncResult(MutableModel):
    subscription_id: str = Field(description="订阅 id")
    new_items: int = Field(default=0, description="新增条数")
    inserted: list[FeedItem] = Field(default_factory=list, description="新增条目")
    error: str = Field(default="", description="错误信息")
