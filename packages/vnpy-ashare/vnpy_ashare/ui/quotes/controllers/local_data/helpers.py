"""本地 K 线加载回调守卫。"""

from __future__ import annotations

from vnpy.trader.constant import Exchange


def should_apply_loaded_bars(
    *,
    generation: int,
    current_generation: int,
    request_id: int,
    current_request_id: int,
    target_key: tuple[str, Exchange],
    current_key: tuple[str, Exchange] | None,
    target_scope: str,
    current_scope: str,
    loaded_key: tuple[str, Exchange] | None = None,
) -> bool:
    """K 线回调是否应写入图表（标的、周期、generation 须一致）。"""
    if generation != current_generation:
        return False
    if request_id != current_request_id:
        return False
    if current_key is None or current_key != target_key:
        return False
    if target_scope != current_scope:
        return False
    if loaded_key is not None and loaded_key != target_key:
        return False
    return True
