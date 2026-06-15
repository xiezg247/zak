"""按操作系统选择 VeighNa GUI 可用字体。"""

from __future__ import annotations

import functools
import platform
from typing import cast

WINDOWS_FONTS = ("微软雅黑", "Microsoft YaHei", "SimHei")
MACOS_FONTS = ("PingFang SC", "Helvetica Neue", "Arial")
LINUX_FONTS = ("Noto Sans CJK SC", "WenQuanYi Micro Hei", "Arial")
FALLBACK_FONT = "Arial"

UNAVAILABLE_ON_MACOS = frozenset({"微软雅黑", "Microsoft YaHei", "SimHei", "SimSun", "宋体"})


@functools.lru_cache(maxsize=1)
def _platform_key() -> str:
    return platform.system()


@functools.lru_cache(maxsize=1)
def font_family_candidates() -> tuple[str, ...]:
    """当前平台预置的可选字体列表。"""
    system = _platform_key()
    if system == "Darwin":
        return MACOS_FONTS
    if system == "Windows":
        return WINDOWS_FONTS
    return LINUX_FONTS


def default_font_family() -> str:
    return font_family_candidates()[0]


def resolve_font_family(configured: str | None = None) -> str:
    if not configured or configured in UNAVAILABLE_ON_MACOS:
        if _platform_key() == "Darwin":
            return default_font_family()
    return configured or default_font_family()


@functools.lru_cache(maxsize=1)
def _installed_font_families() -> frozenset[str]:
    from vnpy.trader.ui import QtGui

    return frozenset(QtGui.QFontDatabase.families())


@functools.lru_cache(maxsize=1)
def available_font_families() -> tuple[str, ...]:
    """预置候选字体中，本机已安装的子集。"""
    installed = _installed_font_families()
    matched = [name for name in font_family_candidates() if name in installed]
    if matched:
        return tuple(matched)
    default = resolve_font_family()
    if default in installed:
        return (default,)
    if FALLBACK_FONT in installed:
        return (FALLBACK_FONT,)
    return (default,)


def supports_font_family_selection() -> bool:
    """本机是否有多个可选 UI 字体。"""
    return len(available_font_families()) > 1


def clear_font_cache() -> None:
    """清除字体探测缓存（测试或字体安装变更后）。"""
    _platform_key.cache_clear()
    font_family_candidates.cache_clear()
    _installed_font_families.cache_clear()
    available_font_families.cache_clear()


def app_font_from_settings(settings: dict | None = None):
    """从 SETTINGS 或传入 dict 构建 QFont。"""
    from vnpy.trader.setting import SETTINGS
    from vnpy.trader.ui import QtGui

    src = settings if settings is not None else SETTINGS
    family = resolve_font_family(str(src.get("font.family", "")))
    try:
        size = int(src.get("font.size", 12) or 12)
    except (TypeError, ValueError):
        size = 12
    size = max(8, min(size, 32))
    return QtGui.QFont(family, size)


def apply_app_font(*, settings: dict | None = None) -> bool:
    """将字体应用到 QApplication（GUI 运行时）。"""
    from vnpy.trader.ui import QtWidgets

    app = QtWidgets.QApplication.instance()
    if app is None:
        return False
    cast(QtWidgets.QApplication, app).setFont(app_font_from_settings(settings))
    return True
