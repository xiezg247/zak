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
