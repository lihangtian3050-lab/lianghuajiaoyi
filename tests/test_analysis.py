import unittest

from tests import context  # noqa: F401
from quant_trading.analysis import analyze_market_data
from quant_trading.data import generate_sample_ohlcv
from quant_trading.strategy import moving_average_signal


class AnalysisTests(unittest.TestCase):
    def test_analyze_market_data_returns_clear_fields(self):
        data = generate_sample_ohlcv("SAMPLE", periods=80, seed=9)
        signal = moving_average_signal(data, 5, 20)

        result = analyze_market_data(data, signal, 5, 20)

        self.assertGreater(result.close, 0)
        self.assertIn(result.trend_label, ["短期偏强", "短期偏弱", "震荡或信号不一致"])
        self.assertTrue(result.research_conclusion.startswith("规则研究结论"))
        self.assertTrue(result.risk_notes)


if __name__ == "__main__":
    unittest.main()
