"""悬浮 / 全屏双轨会话 ID 持久化。"""

from __future__ import annotations

from typing import Literal

from vnpy.trader.ui import QtCore

from vnpy_ashare.paths import QSETTINGS_ORG

Surface = Literal["floating", "assistant"]
SURFACES: tuple[Surface, ...] = ("floating", "assistant")

_SETTINGS_ORG = QSETTINGS_ORG
_SETTINGS_APP = "llm_sessions"


class SessionSurfaceStore:
    """各 UI 轨道上次使用的 session_id（内存 + QSettings）。"""

    def __init__(self, settings: QtCore.QSettings | None = None) -> None:
        self._settings = settings or QtCore.QSettings(_SETTINGS_ORG, _SETTINGS_APP)
        self._memory: dict[Surface, str] = {}

    def get(self, surface: Surface, *, fallback: str) -> str:
        if surface in self._memory:
            return self._memory[surface]
        key = f"{surface}_session_id"
        value = self._settings.value(key)
        if isinstance(value, str) and value:
            self._memory[surface] = value
            return value
        return fallback

    def set(self, surface: Surface, session_id: str) -> None:
        self._memory[surface] = session_id
        self._settings.setValue(f"{surface}_session_id", session_id)

    def clear_binding(self, session_id: str, *, replacement: str) -> None:
        for surface in SURFACES:
            if self._memory.get(surface) == session_id:
                self.set(surface, replacement)
