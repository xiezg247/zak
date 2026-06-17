"""笔记中心：跨标的浏览备忘与流水。"""

from __future__ import annotations

from typing import Any

__all__ = [
    "NotesCenterDialog",
    "NotesCenterWidget",
    "show_notes_center_dialog",
]


def __getattr__(name: str) -> Any:
    if name == "NotesCenterDialog":
        from vnpy_ashare.ui.features.notes_center.dialog import NotesCenterDialog

        return NotesCenterDialog
    if name == "NotesCenterWidget":
        from vnpy_ashare.ui.features.notes_center.widget import NotesCenterWidget

        return NotesCenterWidget
    if name == "show_notes_center_dialog":
        from vnpy_ashare.ui.features.notes_center.open import show_notes_center_dialog

        return show_notes_center_dialog
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)
