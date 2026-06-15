"""env_store .env 读写测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from vnpy_ashare.config.bridge import parse_env_file
from vnpy_ashare.config.env_store import env_assignment_line, quote_env_value, save_env_values


class EnvStoreTest(unittest.TestCase):
    def test_quote_env_value(self) -> None:
        self.assertEqual(quote_env_value("plain"), "plain")
        self.assertEqual(quote_env_value("has space"), '"has space"')
        self.assertEqual(quote_env_value('say "hi"'), '"say \\"hi\\""')

    def test_env_assignment_line(self) -> None:
        self.assertEqual(env_assignment_line("LLM_MODEL", "gpt-4"), "LLM_MODEL=gpt-4")

    def test_save_env_values_updates_known_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                "# header\nDATAFEED_NAME=tickflow\nCUSTOM=keep-me\n",
                encoding="utf-8",
            )
            save_env_values({"DATAFEED_NAME": "tushare", "LLM_MODEL": "test-model"}, env_file=path, backup=False)
            text = path.read_text(encoding="utf-8")
            values = parse_env_file(path)
            self.assertIn("# header", text)
            self.assertIn("CUSTOM=keep-me", text)
            self.assertEqual(values["DATAFEED_NAME"], "tushare")
            self.assertEqual(values["LLM_MODEL"], "test-model")

    def test_save_env_values_creates_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            save_env_values({"LLM_API_BASE": "https://api.example.com"}, env_file=path, backup=False)
            self.assertTrue(path.is_file())
            self.assertEqual(parse_env_file(path)["LLM_API_BASE"], "https://api.example.com")


if __name__ == "__main__":
    unittest.main()
