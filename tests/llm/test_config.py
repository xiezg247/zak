"""LLM 配置测试。"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy_llm.config.settings import load_llm_config


class TestLlmConfig(unittest.TestCase):
    def test_load_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env_file = Path(tmp) / ".env"
            env_file.write_text(
                "LLM_API_KEY=test-key-12345678\nLLM_API_BASE=https://example.com/v1\nLLM_MODEL=gpt-4o\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                with patch("vnpy_llm.config.settings.Path.cwd", return_value=Path(tmp)):
                    cfg = load_llm_config()
            self.assertTrue(cfg.configured)
            self.assertEqual(cfg.api_base, "https://example.com/v1")
            self.assertEqual(cfg.model, "gpt-4o")
            self.assertIn("...", cfg.masked_key())

    def test_not_configured_without_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with patch("vnpy_llm.config.settings.Path.cwd", return_value=Path("/nonexistent")):
                with patch("vnpy_llm.config.settings.load_dotenv"):
                    cfg = load_llm_config()
        self.assertFalse(cfg.configured)


if __name__ == "__main__":
    unittest.main()
