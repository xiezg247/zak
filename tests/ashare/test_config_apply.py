"""config.apply 分级热应用测试。"""

from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from vnpy.trader.setting import SETTINGS

from vnpy_ashare.config.apply import (
    ApplyContext,
    apply_runtime_settings,
    diff_settings,
    env_apply_tier,
    format_apply_summary,
    vt_apply_tier,
)


class ConfigApplyTierTest(unittest.TestCase):
    def test_vt_log_instant(self) -> None:
        self.assertEqual(vt_apply_tier("log.level"), "instant")
        self.assertEqual(vt_apply_tier("log.active"), "instant")

    def test_vt_font_instant(self) -> None:
        self.assertEqual(vt_apply_tier("font.family"), "instant")
        self.assertEqual(vt_apply_tier("font.size"), "instant")

    def test_vt_datafeed_soft(self) -> None:
        self.assertEqual(vt_apply_tier("datafeed.name"), "soft_reload")

    def test_vt_database_restart(self) -> None:
        self.assertEqual(vt_apply_tier("database.name"), "restart_required")

    def test_env_llm_instant(self) -> None:
        self.assertEqual(env_apply_tier("LLM_API_KEY"), "instant")

    def test_env_notify_instant(self) -> None:
        self.assertEqual(env_apply_tier("NOTIFY_ENABLED"), "instant")
        self.assertEqual(env_apply_tier("FEISHU_WEBHOOK_URL"), "instant")

    def test_env_database_restart(self) -> None:
        self.assertEqual(env_apply_tier("DATABASE_NAME"), "restart_required")


class DiffSettingsTest(unittest.TestCase):
    def test_diff_only_changed(self) -> None:
        previous = {"log.level": "INFO", "font.size": 12}
        updates = {"log.level": "DEBUG", "font.size": 12}
        self.assertEqual(diff_settings(previous, updates), {"log.level": "DEBUG"})


class ApplyRuntimeSettingsTest(unittest.TestCase):
    def test_apply_log_level_updates_root_logger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            setting_path = Path(tmp) / "vt_setting.json"
            setting_path.write_text('{"log.level": "DEBUG", "log.active": true}', encoding="utf-8")
            with patch("vnpy_ashare.config.vt_settings.SETTING_FILENAME", setting_path.name):
                with patch("vnpy_ashare.config.vt_settings.load_json", return_value={"log.level": "DEBUG", "log.active": True}):
                    SETTINGS["log.level"] = "INFO"
                    SETTINGS["log.active"] = True
                    results = apply_runtime_settings({"log.level": "DEBUG"})
                    self.assertTrue(results)
                    self.assertEqual(results[0].tier, "instant")
                    self.assertTrue(results[0].success)
                    self.assertGreaterEqual(logging.getLogger().level, logging.DEBUG)

    def test_apply_font_instant(self) -> None:
        with patch("vnpy_ashare.config.apply._apply_font_settings", return_value=True):
            results = apply_runtime_settings({"font.size": 14})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].tier, "instant")
        self.assertTrue(results[0].success)

    def test_apply_datafeed_soft_reload(self) -> None:
        with patch("vnpy_ashare.config.apply._reload_datafeed_stack", return_value=(True, "已重建 datafeed（tickflow）")):
            results = apply_runtime_settings({"datafeed.password": "new-key"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].tier, "soft_reload")
        self.assertTrue(results[0].success)
        self.assertIn("datafeed", results[0].message)

    def test_apply_database_reports_restart(self) -> None:
        results = apply_runtime_settings({"database.name": "postgresql"})
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].tier, "restart_required")
        self.assertIn("重启", results[0].message)

    def test_apply_llm_via_context(self) -> None:
        engine = MagicMock()
        cfg = MagicMock()
        cfg.configured = True
        cfg.model = "gpt-test"
        cfg.api_base = "https://api.example.com"
        engine.reload_config.return_value = cfg
        ctx = ApplyContext(llm_engine=engine)
        from vnpy_ashare.config.apply import apply_llm_reload

        result = apply_llm_reload(ctx)
        self.assertTrue(result.success)
        engine.reload_config.assert_called_once()

    def test_format_apply_summary(self) -> None:
        from vnpy_ashare.config.apply import ApplyResult

        text = format_apply_summary(
            "/tmp/vt_setting.json",
            [
                ApplyResult("log.level", "日志级别", "instant", True, "已立即生效"),
                ApplyResult("database.name", "K 线数据库类型", "restart_required", True, "已保存，需重启应用后生效"),
            ],
        )
        self.assertIn("日志级别", text)
        self.assertIn("K 线数据库类型", text)
        self.assertIn("⚠", text)


class DatafeedReloadTest(unittest.TestCase):
    def test_reload_datafeed_stack_resets_providers(self) -> None:
        with patch("vnpy_ashare.config.datafeed_reload.reload_vnpy_datafeed", return_value=(True, "已重建")):
            with patch("vnpy_ashare.quotes.core.provider.reset_quote_providers") as reset_mock:
                from vnpy_ashare.config.datafeed_reload import reload_datafeed_stack

                ok, msg = reload_datafeed_stack()
        self.assertTrue(ok)
        self.assertEqual(msg, "已重建")
        reset_mock.assert_called_once()

    def test_reload_vnpy_datafeed_clears_cached_instance(self) -> None:
        import vnpy.trader.datafeed as datafeed_module

        datafeed_module.datafeed = MagicMock()
        new_instance = MagicMock()
        with patch("vnpy.trader.datafeed.get_datafeed", return_value=new_instance):
            from vnpy_ashare.config.datafeed_reload import reload_vnpy_datafeed

            ok, _msg = reload_vnpy_datafeed()
        self.assertTrue(ok)
        new_instance.init.assert_called_once()


if __name__ == "__main__":
    unittest.main()
