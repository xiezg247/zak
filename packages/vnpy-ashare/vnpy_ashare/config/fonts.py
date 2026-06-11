"""按操作系统选择 VeighNa GUI 可用字体。"""

from __future__ import annotations

import platform

WINDOWS_FONTS = ("微软雅黑", "Microsoft YaHei", "SimHei")
MACOS_FONTS = ("PingFang SC", "Helvetica Neue", "Arial")
LINUX_FONTS = ("Noto Sans CJK SC", "WenQuanYi Micro Hei", "Arial")
FALLBACK_FONT = "Arial"

UNAVAILABLE_ON_MACOS = frozenset({"微软雅黑", "Microsoft YaHei", "SimHei", "SimSun", "宋体"})


def default_font_family() -> str:
    system = platform.system()
    if system == "Darwin":
        return MACOS_FONTS[0]
    if system == "Windows":
        return WINDOWS_FONTS[0]
    return LINUX_FONTS[0]


def resolve_font_family(configured: str | None = None) -> str:
    if not configured or configured in UNAVAILABLE_ON_MACOS:
        if platform.system() == "Darwin":
            return default_font_family()
    return configured or default_font_family()


def font_family_candidates() -> tuple[str, ...]:
    """当前平台预置的可选字体列表。"""
    system = platform.system()
    if system == "Darwin":
        return MACOS_FONTS
    if system == "Windows":
        return WINDOWS_FONTS
    return LINUX_FONTS


def available_font_families() -> tuple[str, ...]:
    """预置候选字体中，本机已安装的子集。"""
    from vnpy.trader.ui import QtGui

    installed = set(QtGui.QFontDatabase.families())
    matched = [name for name in font_family_candidates() if name in installed]
    if matched:
        return tuple(matched)
    return (resolve_font_family(),)


def supports_font_family_selection() -> bool:
    """本机是否有多个可选 UI 字体。"""
    return len(available_font_families()) > 1
