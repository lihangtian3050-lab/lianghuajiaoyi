import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from tests import context  # noqa: F401
from quant_trading.data_cache import CacheKey, get_or_fetch_a_share_history, load_cached_history, save_cached_history
from quant_trading.data_sources import DataSourceConfig


def sample_data(close=10.3):
    frame = pd.DataFrame(
        {
            "date": pd.bdate_range("2024-01-02", periods=2),
            "symbol": ["000001", "000001"],
            "open": [close - 0.3, close],
            "high": [close + 0.5, close + 0.5],
            "low": [close - 0.5, close - 0.5],
            "close": [close, close + 0.2],
            "volume": [1000, 1200],
        }
    )
    frame.attrs["source"] = "akshare-sina"
    return frame


class DataCacheTests(unittest.TestCase):
    def test_save_and_load_cached_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "market.sqlite"
            key = CacheKey("000001", "20240101", "20240131", "auto", "qfq")

            save_cached_history(cache_path, key, sample_data())
            loaded = load_cached_history(cache_path, key)

            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.attrs["source"], "akshare-sina")
            self.assertEqual(loaded["close"].round(2).tolist(), [10.3, 10.5])

    def test_cache_hit_does_not_fetch_again(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "market.sqlite"
            config = DataSourceConfig(source="auto", adjust="qfq")

            with patch("quant_trading.data_cache.fetch_a_share_history", return_value=sample_data()) as fetch:
                first = get_or_fetch_a_share_history("000001", "20240101", "20240131", cache_path, config)
                second = get_or_fetch_a_share_history("000001", "20240101", "20240131", cache_path, config)

            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(first.attrs["cache_status"], "refreshed")
            self.assertEqual(second.attrs["cache_status"], "hit")

    def test_refresh_overwrites_cached_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "market.sqlite"
            config = DataSourceConfig(source="auto", adjust="qfq")

            with patch("quant_trading.data_cache.fetch_a_share_history", side_effect=[sample_data(10.3), sample_data(20.0)]):
                get_or_fetch_a_share_history("000001", "20240101", "20240131", cache_path, config)
                refreshed = get_or_fetch_a_share_history(
                    "000001",
                    "20240101",
                    "20240131",
                    cache_path,
                    config,
                    refresh=True,
                )

            self.assertEqual(refreshed["close"].round(2).tolist(), [20.0, 20.2])


if __name__ == "__main__":
    unittest.main()
