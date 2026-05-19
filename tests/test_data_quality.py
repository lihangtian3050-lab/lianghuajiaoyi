import unittest
from unittest.mock import patch

import pandas as pd

from tests import context  # noqa: F401
from quant_trading.data_quality import cross_check_a_share_sources


def sample_data(close_values, dates=None, open_values=None, high_values=None, low_values=None):
    if dates is None:
        dates = pd.bdate_range("2024-01-02", periods=len(close_values))
    open_values = open_values or close_values
    high_values = high_values or [max(open_value, close_value) + 0.5 for open_value, close_value in zip(open_values, close_values)]
    low_values = low_values or [min(open_value, close_value) - 0.5 for open_value, close_value in zip(open_values, close_values)]
    frame = pd.DataFrame(
        {
            "date": dates,
            "symbol": ["000001"] * len(close_values),
            "open": open_values,
            "high": high_values,
            "low": low_values,
            "close": close_values,
            "volume": [1000] * len(close_values),
        }
    )
    frame.attrs["cache_status"] = "disabled"
    return frame


class DataQualityTests(unittest.TestCase):
    def test_cross_check_reports_price_differences(self):
        def fake_fetch(symbol, start_date, end_date, config):
            if config.source == "source-a":
                data = sample_data([10.0, 10.0], open_values=[9.8, 9.8], high_values=[11.0, 11.0], low_values=[9.0, 9.0])
            else:
                data = sample_data([10.0, 10.5], open_values=[9.8, 10.2], high_values=[11.0, 11.0], low_values=[9.0, 9.0])
            data.attrs["source"] = config.source
            return data

        with patch("quant_trading.data_quality.fetch_a_share_history", side_effect=fake_fetch):
            result = cross_check_a_share_sources(
                "000001",
                "20240101",
                "20240131",
                ["source-a", "source-b"],
                cache_path=None,
                price_tolerance=0.01,
            )

        self.assertFalse(result.passed)
        self.assertEqual(result.differences["column"].tolist(), ["close", "open"])
        self.assertTrue(result.missing_dates.empty)

    def test_cross_check_reports_missing_dates(self):
        full_dates = pd.bdate_range("2024-01-02", periods=2)

        def fake_fetch(symbol, start_date, end_date, config):
            if config.source == "source-a":
                data = sample_data([10.0, 10.1], full_dates)
            else:
                data = sample_data([10.0], full_dates[:1])
            data.attrs["source"] = config.source
            return data

        with patch("quant_trading.data_quality.fetch_a_share_history", side_effect=fake_fetch):
            result = cross_check_a_share_sources(
                "000001",
                "20240101",
                "20240131",
                ["source-a", "source-b"],
                cache_path=None,
            )

        self.assertFalse(result.passed)
        self.assertEqual(len(result.missing_dates), 1)
        self.assertEqual(result.missing_dates["source"].iloc[0], "source-b")


if __name__ == "__main__":
    unittest.main()
