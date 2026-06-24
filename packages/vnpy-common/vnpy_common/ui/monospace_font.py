"""等宽字体：Qt 会把 CSS generic ``monospace`` 误当成字体族名，故只用系统已安装字体。"""

from __future__ import annotations

import platform

from vnpy.trader.ui import QtGui


def monospace_font_css_stack(*, quoted: bool = False) -> str:
    """QSS / HTML 用等宽 font-family 列表（不含 ``monospace`` 关键字）。"""
    system = platform.system()
    if system == "Darwin":
        names = ("Menlo", "Monaco", "Courier New")
    elif system == "Windows":
        names = ("Consolas", "Courier New")
    else:
        names = ("DejaVu Sans Mono", "Courier New")
    if quoted:
        return ", ".join(f'"{name}"' for name in names)
    return ", ".join(f'"{name}"' if " " in name else name for name in names)


def apply_system_monospace_font(font: QtGui.QFont) -> QtGui.QFont:
    """交给 Qt 按系统默认挑选等宽字体（不硬编码字体族名）。"""
    out = QtGui.QFont(font)
    out.setStyleHint(QtGui.QFont.StyleHint.Monospace)
    out.setFixedPitch(True)
    return out
