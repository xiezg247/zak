"""多因子选股配方持久化（供定时任务引用）。"""

from __future__ import annotations

import json
import uuid
from typing import Any, Literal

from pydantic import Field

from vnpy_ashare.domain.time.china import format_china_datetime
from vnpy_ashare.storage.repository.app import AppUserScopedRepository
from vnpy_common.domain.base import MutableModel
from vnpy_common.storage.compat import DbRow
from vnpy_common.storage.tables import screener_recipes as sr

TriggerKind = Literal["intraday", "post_close"]

_RECIPE_COLUMNS = (sr.c.id, sr.c.name, sr.c.trigger_kind, sr.c.config_json, sr.c.created_at, sr.c.updated_at)


class SavedRecipe(MutableModel):
    """用户保存的多因子选股配方。"""

    id: str = Field(description="配方 id")
    name: str = Field(description="配方名称")
    trigger_kind: TriggerKind = Field(description="触发类型（盘中/盘后）")
    config: dict[str, Any] = Field(description="配方配置")
    created_at: str = Field(description="创建时间")
    updated_at: str = Field(description="更新时间")


def _now() -> str:
    return format_china_datetime()


def _row_to_saved(row: DbRow) -> SavedRecipe:
    return SavedRecipe(
        id=str(row["id"]),
        name=str(row["name"]),
        trigger_kind=str(row["trigger_kind"]),  # type: ignore[arg-type]
        config=json.loads(str(row["config_json"] or "{}")),
        created_at=str(row["created_at"]),
        updated_at=str(row["updated_at"]),
    )


class ScreenerRecipeRepository(AppUserScopedRepository):
    table = sr

    def list_recipes(self, *, trigger_kind: TriggerKind | None = None) -> list[SavedRecipe]:
        extras = (sr.c.trigger_kind == trigger_kind,) if trigger_kind else ()
        rows = self.list_for_user(*_RECIPE_COLUMNS, extras=extras or None, order_by=(sr.c.updated_at.desc(),))
        return [_row_to_saved(row) for row in rows]

    def get_recipe(self, recipe_id: str) -> SavedRecipe | None:
        rows = self.list_for_user(*_RECIPE_COLUMNS, extras=(sr.c.id == recipe_id,), limit=1)
        return _row_to_saved(rows[0]) if rows else None

    def save_recipe(
        self,
        name: str,
        *,
        trigger_kind: TriggerKind,
        config: dict[str, Any],
        recipe_id: str | None = None,
    ) -> SavedRecipe:
        cleaned = name.strip()
        if not cleaned:
            raise ValueError("配方名称不能为空")
        now = _now()
        payload = json.dumps(config, ensure_ascii=False)
        if recipe_id:
            updated = self.update_matching(
                {
                    "name": cleaned,
                    "trigger_kind": trigger_kind,
                    "config_json": payload,
                    "updated_at": now,
                },
                self.scope(sr.c.id == recipe_id),
            )
            if updated == 0:
                raise RuntimeError("保存选股配方失败")
            sid = recipe_id
        else:
            sid = uuid.uuid4().hex
            self.insert_one_for_user(
                id=sid,
                name=cleaned,
                trigger_kind=trigger_kind,
                config_json=payload,
                created_at=now,
                updated_at=now,
            )
        saved = self.get_recipe(sid)
        if saved is None:
            raise RuntimeError("保存选股配方失败")
        return saved

    def delete_recipe(self, recipe_id: str) -> bool:
        return self.delete_matching(self.scope(sr.c.id == recipe_id)) > 0


_repo = ScreenerRecipeRepository()


def list_saved_recipes(*, trigger_kind: TriggerKind | None = None) -> list[SavedRecipe]:
    return _repo.list_recipes(trigger_kind=trigger_kind)


def get_saved_recipe(recipe_id: str) -> SavedRecipe | None:
    return _repo.get_recipe(recipe_id)


def save_recipe(
    name: str,
    *,
    trigger_kind: TriggerKind,
    config: dict[str, Any],
    recipe_id: str | None = None,
) -> SavedRecipe:
    return _repo.save_recipe(name, trigger_kind=trigger_kind, config=config, recipe_id=recipe_id)


def delete_recipe(recipe_id: str) -> bool:
    return _repo.delete_recipe(recipe_id)
