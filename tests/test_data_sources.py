import sys
import types
import unittest

import pandas as pd

from tests import context  # noqa: F401
from quant_trading.data_sources import DataSourceConfig, fetch_a_share_history


class DataSourceTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("akshare", None)

    def test_fetch_eastmoney_normalizes_akshare_columns(self):
        fake_akshare = types.SimpleNamespace(
            stock_zh_a_hist=lambda **kwargs: pd.DataFrame(
                {
                    "日期": ["2024-01-02", "2024-01-03"],
                    "股票代码": ["000001", "000001"],
                    "开盘": [10.0, 10.2],
                    "最高": [10.5, 10.8],
                    "最低": [9.9, 10.1],
                    "收盘": [10.3, 10.6],
                    "成交量": [1000, 1200],
                }
            )
        )
        sys.modules["akshare"] = fake_akshare

        data = fetch_a_share_history("sz000001", "2024-01-01", "2024-01-31")

        self.assertEqual(data.columns.tolist(), ["date", "symbol", "open", "high", "low", "close", "volume"])
        self.assertEqual(data["symbol"].tolist(), ["000001", "000001"])
        self.assertEqual(data["close"].tolist(), [10.3, 10.6])

    def test_fetch_sina_uses_market_prefixed_symbol(self):
        captured = {}

        def fake_daily(**kwargs):
            captured.update(kwargs)
            return pd.DataFrame(
                {
                    "date": ["2024-01-02"],
                    "open": [10.0],
                    "high": [10.5],
                    "low": [9.9],
                    "close": [10.3],
                    "volume": [1000],
                }
            )

        sys.modules["akshare"] = types.SimpleNamespace(stock_zh_a_daily=fake_daily)

        fetch_a_share_history("600519", "20240101", "20240131", DataSourceConfig(source="akshare-sina"))

        self.assertEqual(captured["symbol"], "sh600519")

    def test_fetch_tencent_maps_amount_to_volume(self):
        sys.modules["akshare"] = types.SimpleNamespace(
            stock_zh_a_hist_tx=lambda **kwargs: pd.DataFrame(
                {
                    "date": ["2024-01-02"],
                    "open": [10.0],
                    "close": [10.3],
                    "high": [10.5],
                    "low": [9.9],
                    "amount": [1000],
                }
            )
        )

        data = fetch_a_share_history("000001", "20240101", "20240131", DataSourceConfig(source="akshare-tencent"))

        self.assertEqual(data["volume"].tolist(), [1000])

    def test_auto_records_successful_source(self):
        fake_akshare = types.SimpleNamespace(
            stock_zh_a_hist=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("eastmoney down")),
            stock_zh_a_daily=lambda **kwargs: pd.DataFrame(
                {
                    "date": ["2024-01-02"],
                    "open": [10.0],
                    "high": [10.5],
                    "low": [9.9],
                    "close": [10.3],
                    "volume": [1000],
                }
            ),
        )
        sys.modules["akshare"] = fake_akshare

        data = fetch_a_share_history("000001", "20240101", "20240131", DataSourceConfig(source="auto"))

        self.assertEqual(data.attrs["source"], "akshare-sina")


if __name__ == "__main__":
    unittest.main()
