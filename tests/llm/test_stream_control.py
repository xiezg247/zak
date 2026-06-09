"""流式中断与配置重载测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from vnpy.event import EventEngine
from vnpy.trader.engine import MainEngine
from vnpy.trader.ui import QtWidgets

import tests._bootstrap  # noqa: F401
from vnpy_llm.client import StreamCancelled
from vnpy_llm.config import LlmConfig
from vnpy_llm.engine import LlmEngine


class StreamCancelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmp_dir.name) / "chat.db"
        self._store_patcher = patch("vnpy_llm.store.CHAT_DB_PATH", self._db_path)
        self._store_patcher.start()

        self.main_engine = MagicMock(spec=MainEngine)
        self.main_engine.engines = {}
        self.event_engine = EventEngine()
        with (
            patch("vnpy_ashare.ai.context_store.register_context_listener"),
            patch.object(
                LlmEngine,
                "_emit_tools_status",
            ),
        ):
            self.engine = LlmEngine(self.main_engine, self.event_engine)
        self.engine.config = LlmConfig(
            api_base="https://example.com/v1",
            api_key="test-key",
            model="test-model",
            max_tokens=128,
            temperature=0.7,
        )

    def tearDown(self) -> None:
        self._store_patcher.stop()
        self._tmp_dir.cleanup()

    def test_request_cancel_sets_flag(self) -> None:
        self.engine._streaming = True
        self.engine.request_cancel_stream()
        self.assertTrue(self.engine._cancel_requested)

    def test_stream_reply_cancel_persists_partial(self) -> None:
        cancelled: list[bool] = []
        self.engine.signals.stream_cancelled.connect(lambda: cancelled.append(True))

        def fake_stream(*_args, **kwargs):
            should_cancel = kwargs.get("should_cancel")
            yield "部分"
            if should_cancel and should_cancel():
                raise StreamCancelled("用户已停止生成")
            yield "不应出现"

        with (
            patch("vnpy_llm.engine.stream_chat_completion", side_effect=fake_stream),
            patch.object(
                self.engine,
                "_get_openai_tools",
                return_value=[],
            ),
        ):
            gen = self.engine.stream_reply("你好")
            self.assertEqual(next(gen), "部分")
            self.engine.request_cancel_stream()
            with self.assertRaises(StopIteration):
                next(gen)

        messages = self.engine.get_messages()
        assistant = [msg for msg in messages if msg.role == "assistant"]
        self.assertEqual(len(assistant), 1)
        self.assertEqual(assistant[0].content, "部分")
        self.assertTrue(cancelled)


class ReloadConfigTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    def test_reload_config_returns_new_config(self) -> None:
        main_engine = MagicMock(spec=MainEngine)
        main_engine.engines = {}
        with (
            patch("vnpy_ashare.ai.context_store.register_context_listener"),
            patch.object(
                LlmEngine,
                "_emit_tools_status",
            ),
        ):
            engine = LlmEngine(main_engine, EventEngine())
        new_cfg = LlmConfig(
            api_base="https://new.example/v1",
            api_key="abc",
            model="new-model",
            max_tokens=2048,
            temperature=0.5,
        )
        with patch("vnpy_llm.engine.load_llm_config", return_value=new_cfg):
            loaded = engine.reload_config()
        self.assertEqual(loaded.model, "new-model")
        self.assertEqual(engine.config.model, "new-model")


if __name__ == "__main__":
    unittest.main()
