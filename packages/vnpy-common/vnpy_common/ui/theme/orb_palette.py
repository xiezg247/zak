"""悬浮 AI 球绘制调色板（由 ThemeTokens 推导）。"""

from __future__ import annotations

from dataclasses import dataclass

from vnpy.trader.ui import QtGui

from vnpy_common.ui.theme.tokens import ThemeTokens


@dataclass(frozen=True)
class OrbPalette:
    glow_center: QtGui.QColor
    glow_edge: QtGui.QColor
    attention_ring: QtGui.QColor
    idle_gradient: tuple[tuple[float, QtGui.QColor], ...]
    hover_gradient: tuple[tuple[float, QtGui.QColor], ...]
    rim: QtGui.QColor
    specular: tuple[tuple[float, QtGui.QColor], ...]
    sparkle_primary: QtGui.QColor
    sparkle_secondary: QtGui.QColor
    sparkle_tertiary: QtGui.QColor
    badge_bg: QtGui.QColor
    badge_bg_attention: QtGui.QColor
    badge_text: QtGui.QColor
    badge_text_attention: QtGui.QColor


def _qcolor(hex_color: str, *, alpha: int = 255) -> QtGui.QColor:
    color = QtGui.QColor(hex_color)
    color.setAlpha(alpha)
    return color


def _mix_hex(base: str, other: str, ratio: float) -> str:
    c1 = QtGui.QColor(base)
    c2 = QtGui.QColor(other)
    r = int(c1.red() + (c2.red() - c1.red()) * ratio)
    g = int(c1.green() + (c2.green() - c1.green()) * ratio)
    b = int(c1.blue() + (c2.blue() - c1.blue()) * ratio)
    return QtGui.QColor(r, g, b).name()


def orb_palette(t: ThemeTokens) -> OrbPalette:
    accent = t.accent
    accent_hover = t.accent_hover
    accent_soft = t.accent_soft
    highlight = "#ffffff" if t.id == "dark" else "#eff6ff"
    deep = _mix_hex(accent, "#0f172a" if t.id == "dark" else "#1e3a8a", 0.55)

    idle_gradient = (
        (0.0, _qcolor(highlight, alpha=220 if t.id == "dark" else 255)),
        (0.30, _qcolor(accent_soft)),
        (0.65, _qcolor(accent)),
        (1.0, _qcolor(deep)),
    )
    hover_gradient = (
        (0.0, _qcolor(highlight)),
        (0.28, _qcolor(accent_hover)),
        (0.62, _qcolor(accent)),
        (1.0, _qcolor(deep)),
    )
    glow_base = QtGui.QColor(accent)
    return OrbPalette(
        glow_center=QtGui.QColor(glow_base.red(), glow_base.green(), glow_base.blue(), 56),
        glow_edge=QtGui.QColor(glow_base.red(), glow_base.green(), glow_base.blue(), 0),
        attention_ring=_qcolor(accent_hover, alpha=180),
        idle_gradient=idle_gradient,
        hover_gradient=hover_gradient,
        rim=_qcolor("#ffffff", alpha=55),
        specular=(
            (0.0, _qcolor("#ffffff", alpha=165)),
            (0.55, _qcolor("#ffffff", alpha=45)),
            (1.0, _qcolor("#ffffff", alpha=0)),
        ),
        sparkle_primary=_qcolor("#ffffff", alpha=245),
        sparkle_secondary=_qcolor(highlight, alpha=215),
        sparkle_tertiary=_qcolor(accent_soft, alpha=185),
        badge_bg=_qcolor(t.panel_bg if t.id == "light" else "#1e2434", alpha=230),
        badge_bg_attention=_qcolor(t.run_row_active_bg, alpha=240),
        badge_text=_qcolor(t.run_row_unread),
        badge_text_attention=_qcolor(t.semantic_warning),
    )
