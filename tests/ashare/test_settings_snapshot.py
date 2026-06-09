"""配置页快照与 vt_setting 读写测试。"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from vnpy_ashare.ui.settings_snapshot import (
    collect_editable_values,
    detect_database_mode,
    env_database_name,
    format_database_status,
    is_configured,
    mask_secret,
    parse_env_file,
    resolve_env_config,
    resolve_env_config_database,
    resolve_env_config_general,
    resolve_vt_config,
)
from vnpy_ashare.vt_settings import (
    build_vt_settings,
    default_vt_settings,
    save_runtime_settings,
    sync_vt_settings_from_env,
)


class SettingsSnapshotTest(unittest.TestCase):
    def test_mask_secret(self) -> None:
        self.assertEqual(mask_secret(""), "未配置")
        self.assertEqual(mask_secret("short"), "***")
        self.assertEqual(mask_secret("abcdefghij"), "abcd…ghij")

    def test_is_configured(self) -> None:
        self.assertFalse(is_configured(""))
        self.assertFalse(is_configured("   "))
        self.assertTrue(is_configured("token"))

    def test_parse_env_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text(
                'DATAFEED_NAME=tushare\n# comment\nTICKFLOW_API_KEY="abc"\n',
                encoding="utf-8",
            )
            values = parse_env_file(path)
            self.assertEqual(values["DATAFEED_NAME"], "tushare")
            self.assertEqual(values["TICKFLOW_API_KEY"], "abc")
            self.assertNotIn("# comment", values)

    def test_resolve_env_config_uses_default_without_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            items = resolve_env_config(path)
            datafeed = next(item for item in items if item.spec.key == "DATAFEED_NAME")
            self.assertEqual(datafeed.value, "tickflow")
            self.assertEqual(datafeed.source, "default")

    def test_resolve_env_config_overrides_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("DATAFEED_NAME=tushare\nTUSHARE_TOKEN=secret\n", encoding="utf-8")
            items = resolve_env_config(path)
            datafeed = next(item for item in items if item.spec.key == "DATAFEED_NAME")
            tushare = next(item for item in items if item.spec.key == "TUSHARE_TOKEN")
            self.assertEqual(datafeed.value, "tushare")
            self.assertEqual(datafeed.source, "env")
            self.assertEqual(tushare.value, "secret")
            self.assertEqual(tushare.source, "env")

    def test_resolve_env_config_general_excludes_database(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("DATABASE_NAME=questdb\nQUESTDB_HOST=db.local\n", encoding="utf-8")
            keys = {item.spec.key for item in resolve_env_config_general(path)}
            self.assertNotIn("DATABASE_NAME", keys)
            self.assertNotIn("QUESTDB_HOST", keys)
            self.assertIn("DATAFEED_NAME", keys)

    def test_resolve_env_config_database_by_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("DATABASE_NAME=sqlite\nQUESTDB_HOST=db.local\n", encoding="utf-8")
            sqlite_keys = {
                item.spec.key for item in resolve_env_config_database("sqlite", path)
            }
            questdb_items = resolve_env_config_database("questdb", path)
            questdb_keys = {item.spec.key for item in questdb_items}
            db_name = next(item for item in questdb_items if item.spec.key == "DATABASE_NAME")
            self.assertEqual(sqlite_keys, {"DATABASE_NAME"})
            self.assertIn("QUESTDB_HOST", questdb_keys)
            self.assertIn("DATABASE_NAME", questdb_keys)
            self.assertEqual(db_name.value, "questdb")
            self.assertEqual(db_name.file_value, "sqlite")

    def test_detect_database_mode_uses_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("DATABASE_NAME=questdb\n", encoding="utf-8")
            mode = detect_database_mode(path, runtime_settings={"database.name": "sqlite"})
            self.assertEqual(mode, "sqlite")

    def test_env_database_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".env"
            path.write_text("DATABASE_NAME=questdb\n", encoding="utf-8")
            self.assertEqual(env_database_name(path), "questdb")

    def test_format_database_status(self) -> None:
        text = format_database_status(
            effective="questdb",
            env_name="sqlite",
            editing="questdb",
        )
        self.assertIn("当前生效：questdb", text)
        self.assertIn(".env：sqlite", text)

    def test_collect_editable_values(self) -> None:
        values = collect_editable_values(
            {
                "datafeed.name": "tickflow",
                "email.server": "smtp.qq.com",
                "font.size": 12,
            }
        )
        self.assertEqual(values["datafeed.name"], "tickflow")
        self.assertEqual(values["font.size"], 12)
        self.assertNotIn("email.server", values)

    def test_resolve_vt_config_includes_all_specs(self) -> None:
        items = resolve_vt_config()
        keys = {item.spec.key for item in items}
        self.assertIn("datafeed.name", keys)
        self.assertIn("database.http_port", keys)
        self.assertIn("log.level", keys)


class VtSettingsTest(unittest.TestCase):
    def test_default_vt_settings(self) -> None:
        defaults = default_vt_settings()
        self.assertEqual(defaults["datafeed.name"], "tickflow")
        self.assertEqual(defaults["database.name"], "sqlite")

    @patch.dict(
        "os.environ",
        {
            "DATAFEED_NAME": "tickflow",
            "TICKFLOW_API_KEY": "tf-key",
            "DATABASE_NAME": "sqlite",
        },
        clear=False,
    )
    def test_build_vt_settings_tickflow(self) -> None:
        settings = build_vt_settings()
        self.assertEqual(settings["datafeed.name"], "tickflow")
        self.assertEqual(settings["datafeed.password"], "tf-key")
        self.assertEqual(settings["database.name"], "sqlite")

    def test_save_runtime_settings_merges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            setting_file = Path(tmp) / "vt_setting.json"
            setting_file.write_text(
                json.dumps({"datafeed.name": "tickflow", "email.server": "keep-me"}),
                encoding="utf-8",
            )
            import vnpy_ashare.vt_settings as vt_settings

            original = vt_settings.SETTING_FILE
            try:
                vt_settings.SETTING_FILE = setting_file
                with patch("vnpy_ashare.vt_settings.SETTING_FILENAME", setting_file.name):
                    with patch("vnpy_ashare.vt_settings.load_json", return_value=json.loads(setting_file.read_text())):
                        with patch("vnpy_ashare.vt_settings.save_json") as save_json:
                            save_runtime_settings({"font.size": 14})
                            saved = save_json.call_args[0][1]
                            self.assertEqual(saved["font.size"], 14)
                            self.assertEqual(saved["email.server"], "keep-me")
            finally:
                vt_settings.SETTING_FILE = original

    @patch.dict(
        "os.environ",
        {"DATAFEED_NAME": "tickflow", "DATABASE_NAME": "sqlite"},
        clear=False,
    )
    def test_sync_vt_settings_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            import vnpy_ashare.vt_settings as vt_settings

            target = Path(tmp) / "vt_setting.json"
            original_file = vt_settings.SETTING_FILE
            original_dir = vt_settings.VNTRADER_DIR
            try:
                vt_settings.VNTRADER_DIR = Path(tmp)
                vt_settings.SETTING_FILE = target
                path = sync_vt_settings_from_env(backup=False)
                self.assertEqual(path, target)
                data = json.loads(target.read_text(encoding="utf-8"))
                self.assertEqual(data["datafeed.name"], "tickflow")
            finally:
                vt_settings.SETTING_FILE = original_file
                vt_settings.VNTRADER_DIR = original_dir
