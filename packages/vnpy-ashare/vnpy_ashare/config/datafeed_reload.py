"""VeighNa datafeed 单例重建（配置热重载）。"""

from __future__ import annotations

from collections.abc import Callable

import vnpy.trader.datafeed as datafeed_module
from vnpy.trader.datafeed import get_datafeed
from vnpy.trader.setting import SETTINGS

from vnpy_ashare.quotes.core.provider import reset_quote_providers


def reload_vnpy_datafeed(*, output: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """丢弃 vnpy 全局 datafeed 缓存并按当前 SETTINGS 重建。"""

    datafeed_module.datafeed = None
    sink = output or (lambda _msg: None)
    try:
        instance = get_datafeed()
        if hasattr(instance, "inited"):
            instance.inited = False
        if hasattr(instance, "init"):
            instance.init(output=sink)
    except Exception as exc:
        return False, f"datafeed 重建失败：{exc}"

    name = str(SETTINGS.get("datafeed.name", "") or "未配置")
    return True, f"已重建 datafeed（{name}）"


def reload_datafeed_stack(*, output: Callable[[str], None] | None = None) -> tuple[bool, str]:
    """重建 vnpy datafeed，并重置行情 Provider 懒加载缓存。"""

    ok, message = reload_vnpy_datafeed(output=output)
    reset_quote_providers()
    return ok, message
