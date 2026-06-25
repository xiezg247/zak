"""悬浮 / 全屏双轨会话 ID 持久化。"""

from __future__ import annotations

from typing import Literal

from vnpy.trader.ui import QtCore

from vnpy_ashare.config.preferences._settings import read_migrated_value, write_setting_value
from vnpy_common.paths import QSETTINGS_ORG

Surface = Literal["floating", "assistant"]
SURFACES: tuple[Surface, ...] = ("floating", "assistant")

_LEGACY_SESSION_APP = "llm_sessions"


def _session_key(surface: Surface) -> str:
    return f"llm/session/{surface}_session_id"


def _legacy_session_key(surface: Surface) -> str:
    return f"{surface}_session_id"


class SessionSurfaceStore:
    """各 UI 轨道上次使用的 session_id（内存 + QSettings）。"""

    def __init__(self, settings: QtCore.QSettings | None = None) -> None:
        self._settings = settings
        self._memory: dict[Surface, str] = {}

    def get(self, surface: Surface, *, fallback: str) -> str:
        if surface in self._memory:
            return self._memory[surface]
        if self._settings is not None:
            key = _legacy_session_key(surface)
            value = self._settings.value(key)
            if isinstance(value, str) and value:
                self._memory[surface] = value
                return value
        legacy = ((QSETTINGS_ORG, _LEGACY_SESSION_APP, _legacy_session_key(surface)),)
        value = read_migrated_value(_session_key(surface), legacy, None)
        if isinstance(value, str) and value:
            self._memory[surface] = value
            return value
        return fallback

    def set(self, surface: Surface, session_id: str) -> None:
        self._memory[surface] = session_id
        if self._settings is not None:
            self._settings.setValue(_legacy_session_key(surface), session_id)
        else:
            write_setting_value(_session_key(surface), session_id)

    def clear_binding(self, session_id: str, *, replacement: str) -> None:
        for surface in SURFACES:
            if self._memory.get(surface) == session_id:
                self.set(surface, replacement)
