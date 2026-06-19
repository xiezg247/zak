"""板块资金同步任务测试。"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from vnpy_ashare.jobs.prefetch.sector_flow import sync_sector_flow_daily_job
from vnpy_ashare.storage.repositories.sector_flow_history import load_sector_flow_history


class SectorFlowSyncJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = Path(self._tmpdir.name) / "test.db"
        self._patch = mock.patch(
            "vnpy_ashare.storage.connection._db_path",
            return_value=self._db_path,
        )
        self._patch.start()

    def tearDown(self) -> None:
        self._patch.stop()
        self._tmpdir.cleanup()

    def test_sync_job_writes_history(self) -> None:
        def fake_dc(*, trade_date: str, content_type: str | None = None):
            if content_type == "行业" and trade_date == "20240927":
                return (
                    [
                        {
                            "trade_date": "20240927",
                            "ts_code": "BK001",
                            "name": "互联网服务",
                            "pct_change": 1.0,
                            "net_amount": 1_000_000_000.0,
                            "net_amount_rate": 1.0,
                            "buy_sm_amount_stock": "A",
                        }
                    ],
                    trade_date,
                )
            return [], trade_date

        with (
            mock.patch("vnpy_ashare.jobs.prefetch.sector_flow.get_tushare_pro", return_value=object()),
            mock.patch(
                "vnpy_ashare.jobs.prefetch.sector_flow.iter_trade_date_strs",
                return_value=["20240927"],
            ),
            mock.patch(
                "vnpy_ashare.jobs.prefetch.sector_flow.fetch_moneyflow_ind_dc",
                side_effect=fake_dc,
            ),
            mock.patch(
                "vnpy_ashare.jobs.prefetch.sector_flow.fetch_moneyflow_cnt_ths",
                return_value=([], "20240927"),
            ),
            mock.patch(
                "vnpy_ashare.services.industry_sector.fetch_sw_l2_index_map",
                return_value={"互联网服务": "801750.SI"},
            ),
        ):
            result = sync_sector_flow_daily_job()

        self.assertTrue(result.success)
        history = load_sector_flow_history(sector_id="801750.SI", sector_kind="industry", limit=5)
        self.assertEqual(len(history), 1)
        self.assertAlmostEqual(history[0].net_flow_yi, 10.0)


if __name__ == "__main__":
    unittest.main()
