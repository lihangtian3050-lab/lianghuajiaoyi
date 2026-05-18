import unittest

import pandas as pd

from tests import context  # noqa: F401
from quant_trading.backtest import BacktestConfig, run_backtest


class BacktestTests(unittest.TestCase):
    def test_signal_takes_effect_on_next_bar(self):
        data = pd.DataFrame(
            {
                "date": pd.bdate_range("2024-01-02", periods=4),
                "open": [100, 100, 110, 121],
                "high": [101, 111, 122, 134],
                "low": [99, 99, 109, 120],
                "close": [100, 110, 121, 133.1],
                "volume": [1000, 1000, 1000, 1000],
            }
        )
        signal = pd.Series([1, 1, 1, 1])

        result = run_backtest(data, signal, BacktestConfig(initial_cash=100.0, fee_rate=0.0, slippage_rate=0.0))

        equity = result.equity_curve["equity"].round(6).tolist()
        self.assertEqual(equity, [100.0, 110.0, 121.0, 133.1])
        self.assertEqual(result.equity_curve["position"].tolist(), [0.0, 1.0, 1.0, 1.0])

    def test_transaction_cost_applies_on_position_change(self):
        data = pd.DataFrame(
            {
                "date": pd.bdate_range("2024-01-02", periods=3),
                "open": [100, 100, 100],
                "high": [101, 101, 101],
                "low": [99, 99, 99],
                "close": [100, 100, 100],
                "volume": [1000, 1000, 1000],
            }
        )
        signal = pd.Series([1, 0, 0])

        result = run_backtest(data, signal, BacktestConfig(initial_cash=100.0, fee_rate=0.01, slippage_rate=0.0))

        self.assertAlmostEqual(result.equity_curve["equity"].iloc[-1], 98.01)


if __name__ == "__main__":
    unittest.main()
