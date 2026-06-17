"""A 股回测策略识别（按 MRO 名称与 registry 判定，避免 reload 后基类 identity 变化）。"""

from __future__ import annotations

from strategies.registry import STRATEGY_REGISTRY

_ASHARE_BASE_NAME = "AShareTemplate"


def _registry_class_names() -> frozenset[str]:
    try:
        return frozenset(STRATEGY_REGISTRY)
    except ImportError:
        return frozenset()


def is_ashare_strategy_class(cls: type) -> bool:
    """策略是否继承 AShareTemplate 或已在 strategies.registry 注册。"""
    if cls.__name__ == _ASHARE_BASE_NAME:
        return False
    if any(base.__name__ == _ASHARE_BASE_NAME for base in cls.__mro__[1:]):
        return True
    return cls.__name__ in _registry_class_names()


def filter_ashare_strategy_names(classes: dict[str, type]) -> list[str]:
    return sorted(name for name, cls in classes.items() if is_ashare_strategy_class(cls))
