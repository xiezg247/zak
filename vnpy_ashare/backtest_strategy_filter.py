"""A 股回测策略识别（兼容 importlib.reload 导致的基类 identity 变化）。"""

from __future__ import annotations

_ASHARE_BASE_NAME = "AShareTemplate"
_ASHARE_BASE_MODULE = "strategies.ashare_template"


def is_ashare_strategy_class(cls: type) -> bool:
    """策略是否继承 strategies.ashare_template.AShareTemplate（按 MRO 名称判定）。"""
    if cls.__name__ == _ASHARE_BASE_NAME:
        return False
    return any(base.__name__ == _ASHARE_BASE_NAME and base.__module__ == _ASHARE_BASE_MODULE for base in cls.__mro__)


def filter_ashare_strategy_names(classes: dict[str, type]) -> list[str]:
    return sorted(name for name, cls in classes.items() if is_ashare_strategy_class(cls))
