"""领域模型序列化约定（跨包共用）。

用法分层：

- **进程内完整扁平 dict**（表格 / UI / 管道合并）：``dump_python(model)``
- **瘦身 dict**（配方 enrich、缺省字段省略）：``dump_python(model, exclude_defaults=True)``
- **落库 / API / JSON 边界**：``dump_json(model)``；读侧 ``Model.model_validate(data)``
- **复合扁平行**（``ScreenerResultRow``、``screening_row_to_dict``）：保留领域专用 ``to_dict()``，
  内部行情部分走 ``quote_row_payload``。
"""

from __future__ import annotations

from collections.abc import Mapping, Set
from typing import Any

from pydantic import BaseModel


def dump_python(
    model: BaseModel,
    *,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    exclude: Set[str] | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """``model_dump(mode=\"python\")`` 统一入口。"""
    kwargs: dict[str, Any] = {
        "mode": "python",
        "exclude_defaults": exclude_defaults,
        "exclude_none": exclude_none,
    }
    if exclude is not None:
        kwargs["exclude"] = exclude
    return model.model_dump(**kwargs)


def dump_json(
    model: BaseModel,
    *,
    exclude_defaults: bool = False,
    exclude_none: bool = False,
    exclude: Set[str] | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """``model_dump(mode=\"json\")`` 统一入口（SQLite / HTTP / Skill JSON）。"""
    kwargs: dict[str, Any] = {
        "mode": "json",
        "exclude_defaults": exclude_defaults,
        "exclude_none": exclude_none,
    }
    if exclude is not None:
        kwargs["exclude"] = exclude
    return model.model_dump(**kwargs)
