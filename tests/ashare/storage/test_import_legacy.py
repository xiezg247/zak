"""import-legacy 单元测试（dry-run，无需真实 PostgreSQL）。"""

from __future__ import annotations

import tempfile
import unittest
import uuid
from pathlib import Path

from vnpy_ashare.storage.import_legacy import (
    _open_sqlite,
    _prepare_app_sqlite,
    normalize_user_id,
)


class TestImportLegacyHelpers(unittest.TestCase):
    def test_normalize_user_id_hex(self) -> None:
        raw = uuid.uuid4().hex
        self.assertEqual(normalize_user_id(raw), str(uuid.UUID(hex=raw)))

    def test_prepare_app_sqlite_adds_user_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_path = Path(tmp) / "zak.db"
            conn = _open_sqlite(app_path)
            try:
                conn.execute("CREATE TABLE watchlist (symbol TEXT, exchange TEXT, name TEXT, sort_order INTEGER, PRIMARY KEY(symbol, exchange))")
                conn.execute("INSERT INTO watchlist(symbol, exchange, name, sort_order) VALUES ('600000', 'SSE', '浦发', 0)")
                default_uid = _prepare_app_sqlite(conn)
                conn.commit()
                row = conn.execute("SELECT user_id FROM watchlist").fetchone()
                self.assertEqual(str(row[0]), default_uid)
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
