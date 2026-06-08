"""双轨会话单元测试。"""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import MagicMock, patch

from vnpy.trader.ui import QtCore, QtWidgets

from vnpy_llm.session_surface import SessionSurfaceStore


class SessionSurfaceStoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_persist_and_load_surface_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = QtCore.QSettings(
                f"{tmp}/sessions.ini",
                QtCore.QSettings.Format.IniFormat,
            )
            store = SessionSurfaceStore(settings)
            store.set("floating", "float-abc")
            store.set("assistant", "assist-xyz")

            other = SessionSurfaceStore(
                QtCore.QSettings(
                    f"{tmp}/sessions.ini",
                    QtCore.QSettings.Format.IniFormat,
                )
            )
            self.assertEqual(other.get("floating", fallback="x"), "float-abc")
            self.assertEqual(other.get("assistant", fallback="x"), "assist-xyz")

    def test_clear_binding_replaces_deleted_session(self) -> None:
        settings = QtCore.QSettings()
        store = SessionSurfaceStore(settings)
        store.set("floating", "old-id")
        store.set("assistant", "keep-id")
        store.clear_binding("old-id", replacement="new-id")
        self.assertEqual(store.get("floating", fallback=""), "new-id")
        self.assertEqual(store.get("assistant", fallback=""), "keep-id")


class LlmEngineSurfaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def _make_engine(self) -> object:
        from vnpy_llm.engine import LlmEngine

        main_engine = MagicMock()
        main_engine.engines = {}
        event_engine = MagicMock()
        with patch.object(LlmEngine, "register_event"), patch.object(
            LlmEngine, "_emit_tools_status"
        ), patch("vnpy_ashare.ai.session_context.register_context_listener"):
            engine = LlmEngine(main_engine, event_engine)
        return engine

    def test_switch_surface_restores_independent_sessions(self) -> None:
        engine = self._make_engine()
        floating_id = engine._surface_store.get("floating", fallback=engine.session_id)
        assistant_id = engine._surface_store.get("assistant", fallback=engine.session_id)

        new_floating = engine.new_session(surface="floating", title="悬浮专用")
        self.assertEqual(engine._surface_store.get("floating", fallback=""), new_floating)

        engine.switch_surface("assistant")
        self.assertEqual(engine.session_id, assistant_id)
        self.assertNotEqual(engine.session_id, new_floating)

        engine.switch_surface("floating")
        self.assertEqual(engine.session_id, new_floating)

    def test_open_session_for_ask_new_on_assistant(self) -> None:
        engine = self._make_engine()
        before = engine.session_id
        engine.open_session_for_ask(surface="assistant", new_session=True)
        self.assertEqual(engine.active_surface, "assistant")
        self.assertNotEqual(engine.session_id, before)


if __name__ == "__main__":
    unittest.main()
