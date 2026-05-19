import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests import context  # noqa: F401
from quant_trading.data import generate_sample_ohlcv
from quant_trading.report_workflow import build_html_report_context, generate_html_report


class ReportWorkflowTests(unittest.TestCase):
    def test_build_html_report_context_uses_shared_pipeline(self):
        sample = generate_sample_ohlcv("SAMPLE", periods=80, seed=11)
        sample.attrs["source"] = "test-source"
        sample.attrs["cache_status"] = "hit"

        with patch("quant_trading.report_workflow.get_or_fetch_a_share_history", return_value=sample):
            report_context = build_html_report_context(
                symbol="000001",
                start_date="20240101",
                end_date="20241231",
                source="auto",
                adjust="qfq",
                cache_path="unused.sqlite",
                capital_profile="small-2000",
            )

        self.assertEqual(report_context.symbol, "000001")
        self.assertEqual(report_context.source, "test-source")
        self.assertEqual(report_context.cash, 2_000.0)
        self.assertFalse(report_context.backtest.equity_curve.empty)

    def test_generate_html_report_writes_file(self):
        sample = generate_sample_ohlcv("SAMPLE", periods=80, seed=11)
        sample.attrs["source"] = "test-source"
        sample.attrs["cache_status"] = "hit"

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "dashboard.html"
            with patch("quant_trading.report_workflow.get_or_fetch_a_share_history", return_value=sample):
                generate_html_report(
                    output_path=output,
                    symbol="000001",
                    start_date="20240101",
                    end_date="20241231",
                    source="auto",
                    adjust="qfq",
                    cache_path="unused.sqlite",
                    capital_profile="small-2000",
                )

            self.assertTrue(output.exists())
            self.assertIn("量化交易报告", output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
