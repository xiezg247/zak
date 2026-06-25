"""import-legacy cache 导入辅助测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from vnpy_ashare.storage.import_legacy import (
    _CACHE_SCHEMA,
    _import_cache_dbs,
    _import_cache_from_app_db,
    _open_sqlite,
)


class TestImportLegacyCache(unittest.TestCase):
    def test_import_cache_db_when_pg_table_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            db_path = base / "radar_predict_cache.db"
            conn = _open_sqlite(db_path)
            try:
                conn.executescript(
                    """
                    CREATE TABLE radar_predict_cache (
                        variant TEXT PRIMARY KEY,
                        rows_json TEXT NOT NULL,
                        scanned_total INTEGER NOT NULL DEFAULT 0,
                        excluded_count INTEGER NOT NULL DEFAULT 0,
                        prefilter_total INTEGER NOT NULL DEFAULT 0,
                        refined_total INTEGER NOT NULL DEFAULT 0,
                        kline_missing INTEGER NOT NULL DEFAULT 0,
                        model_label TEXT NOT NULL DEFAULT '',
                        computed_at TEXT NOT NULL
                    );
                    INSERT INTO radar_predict_cache VALUES ('v1', '[]', 0, 0, 0, 0, 0, '', '2026-01-01');
                    """
                )
                conn.commit()
            finally:
                conn.close()

            pg_conn = MagicMock()

            def _execute(sql, params=()):
                cursor = MagicMock()
                if "information_schema.tables" in sql:
                    cursor.fetchone.return_value = {"?column?": 1}
                elif "information_schema.columns" in sql:
                    cursor.fetchall.return_value = [
                        {"column_name": "variant"},
                        {"column_name": "rows_json"},
                        {"column_name": "scanned_total"},
                        {"column_name": "excluded_count"},
                        {"column_name": "prefilter_total"},
                        {"column_name": "refined_total"},
                        {"column_name": "kline_missing"},
                        {"column_name": "model_label"},
                        {"column_name": "computed_at"},
                    ]
                elif "SELECT COUNT(*)" in sql:
                    cursor.fetchone.return_value = {"c": 0}
                else:
                    cursor.rowcount = 1
                return cursor

            pg_conn.execute.side_effect = _execute

            with patch("vnpy_ashare.storage.import_legacy._pg_table_exists", return_value=True):
                results = _import_cache_dbs(base, pg_conn, dry_run=True)
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].schema, _CACHE_SCHEMA)
            self.assertEqual(results[0].table, "radar_predict_cache")
            self.assertEqual(results[0].rows_read, 1)

    def test_import_cache_from_app_db_skips_missing_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_path = Path(tmp) / "zak.db"
            conn = _open_sqlite(app_path)
            try:
                conn.execute("CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
                conn.commit()
            finally:
                conn.close()
            pg_conn = MagicMock()
            results = _import_cache_from_app_db(app_path, pg_conn, dry_run=True)
            self.assertEqual(results, [])

    def test_cache_only_conflicts_with_skip_cache(self) -> None:
        from vnpy_ashare.storage.import_legacy import ImportLegacyOptions, import_legacy

        with patch("vnpy_ashare.storage.import_legacy.require_database_url", return_value="postgresql://test"):
            with patch("vnpy_ashare.storage.import_legacy.resolve_database_url", return_value="postgresql://x"):
                with self.assertRaises(RuntimeError):
                    import_legacy(ImportLegacyOptions(cache_only=True, skip_cache=True))


if __name__ == "__main__":
    unittest.main()
