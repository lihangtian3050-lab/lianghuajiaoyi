import unittest

import pandas as pd

from tests import context  # noqa: F401
from quant_trading.data import generate_sample_ohlcv, validate_ohlcv


class DataValidationTests(unittest.TestCase):
    def test_generated_sample_is_valid_and_reproducible(self):
        first = generate_sample_ohlcv("SAMPLE", periods=5, seed=7)
        second = generate_sample_ohlcv("SAMPLE", periods=5, seed=7)

        validate_ohlcv(first)
        pd.testing.assert_frame_equal(first, second)

    def test_rejects_duplicate_dates(self):
        data = generate_sample_ohlcv("SAMPLE", periods=3, seed=7)
        data.loc[1, "date"] = data.loc[0, "date"]

        with self.assertRaisesRegex(ValueError, "duplicates"):
            validate_ohlcv(data)

    def test_rejects_inconsistent_high_low(self):
        data = generate_sample_ohlcv("SAMPLE", periods=3, seed=7)
        data.loc[0, "high"] = data.loc[0, "close"] - 1

        with self.assertRaisesRegex(ValueError, "high"):
            validate_ohlcv(data)


if __name__ == "__main__":
    unittest.main()
