"""Tushare 客户端与网络重试测试。"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import requests

from vnpy_ashare.integrations.tushare.client import (
    _apply_api_base,
    _wrap_query_with_transient_retry,
    get_tushare_pro,
    resolve_tushare_api_base,
)
from vnpy_ashare.integrations.tushare.rate_limit import is_transient_network_error, transient_retry_delay


class TushareClientTests(unittest.TestCase):
    def test_resolve_api_base_default(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertEqual(resolve_tushare_api_base(), "https://api.tushare.pro/dataapi")

    def test_resolve_api_base_from_env(self) -> None:
        with patch.dict("os.environ", {"TUSHARE_API_URL": "http://api.waditu.com/dataapi/"}, clear=True):
            self.assertEqual(resolve_tushare_api_base(), "http://api.waditu.com/dataapi")

    def test_apply_api_base(self) -> None:
        pro = MagicMock()
        pro._DataApi__http_url = "http://api.waditu.com/dataapi"
        with patch("vnpy_ashare.integrations.tushare.client.resolve_tushare_api_base", return_value="https://api.tushare.pro/dataapi"):
            _apply_api_base(pro)
        self.assertEqual(pro._DataApi__http_url, "https://api.tushare.pro/dataapi")

    def test_query_retries_transient_network_error(self) -> None:
        pro = MagicMock()
        err = requests.exceptions.ConnectionError("HTTPConnectionPool(host='api.waditu.com', port=80): Failed to resolve 'api.waditu.com'")
        original_query = MagicMock(side_effect=[err, err, {"ok": True}])
        pro.query = original_query
        wrapped = _wrap_query_with_transient_retry(pro)
        with patch("vnpy_ashare.integrations.tushare.client.time.sleep"):
            result = wrapped.query("daily", fields="close", ts_code="000155.SZ")
        self.assertEqual(result, {"ok": True})
        self.assertEqual(original_query.call_count, 3)

    def test_query_does_not_retry_business_error(self) -> None:
        pro = MagicMock()
        original_query = MagicMock(side_effect=Exception("抱歉，您没有接口访问权限"))
        pro.query = original_query
        wrapped = _wrap_query_with_transient_retry(pro)
        with self.assertRaisesRegex(Exception, "接口访问权限"):
            wrapped.query("daily")
        self.assertEqual(original_query.call_count, 1)

    @patch("vnpy_ashare.integrations.tushare.client.ts")
    def test_get_tushare_pro_wraps_client(self, mock_ts: MagicMock) -> None:
        pro = MagicMock()
        mock_ts.pro_api.return_value = pro
        with patch.dict("os.environ", {"TUSHARE_TOKEN": "test-token"}, clear=True):
            with patch("vnpy_ashare.integrations.tushare.client.load_dotenv"):
                with patch("vnpy_ashare.integrations.tushare.client._apply_api_base") as apply_base:
                    with patch("vnpy_ashare.integrations.tushare.client._wrap_query_with_transient_retry", side_effect=lambda item: item) as wrap:
                        result = get_tushare_pro()
        self.assertIs(result, pro)
        apply_base.assert_called_once_with(pro)
        wrap.assert_called_once_with(pro)


class TransientNetworkErrorTests(unittest.TestCase):
    def test_detects_connection_error(self) -> None:
        err = requests.exceptions.ConnectionError("Failed to resolve 'api.waditu.com'")
        self.assertTrue(is_transient_network_error(err))

    def test_detects_dns_message(self) -> None:
        self.assertTrue(is_transient_network_error(Exception("nodename nor servname provided, or not known")))

    def test_ignores_permission_error(self) -> None:
        self.assertFalse(is_transient_network_error(Exception("抱歉，您没有接口访问权限")))

    def test_transient_retry_delay_backoff(self) -> None:
        self.assertEqual(transient_retry_delay(0), 1.0)
        self.assertEqual(transient_retry_delay(1), 2.0)
        self.assertEqual(transient_retry_delay(5), 8.0)


if __name__ == "__main__":
    unittest.main()
