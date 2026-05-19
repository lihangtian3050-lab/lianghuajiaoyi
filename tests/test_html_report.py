import tempfile
import unittest
from pathlib import Path

from tests import context  # noqa: F401
from quant_trading.analysis import analyze_market_data
from quant_trading.backtest import BacktestConfig, run_backtest
from quant_trading.data import generate_sample_ohlcv
from quant_trading.html_report import HtmlReportContext, render_html_report, write_html_report
from quant_trading.news import NewsCheck
from quant_trading.risk import RiskConfig, RiskDecision
from quant_trading.strategy import moving_average_signal
from quant_trading.trading import BUY, Order


class HtmlReportTests(unittest.TestCase):
    def test_render_html_report_contains_key_sections(self):
        data = generate_sample_ohlcv("SAMPLE", periods=60, seed=7)
        signal = moving_average_signal(data, 5, 20)
        backtest = run_backtest(data, signal, BacktestConfig(initial_cash=2_000))
        analysis = analyze_market_data(data, signal, 5, 20)
        news = NewsCheck(items=[], status="empty", message="无新闻", verification_links=[])

        html = render_html_report(
            HtmlReportContext(
                symbol="000001",
                trade_date="2024-03-29",
                source="akshare-sina",
                cache_status="hit",
                capital_profile="small-2000",
                cash=2_000,
                latest_close=10.0,
                latest_signal=1.0,
                risk_config=RiskConfig(),
                order=Order("000001", BUY, 100, 10.0, "test"),
                decision=RiskDecision(True, []),
                backtest=backtest,
                analysis=analysis,
                news=news,
            )
        )

        self.assertIn("000001 量化研究报告", html)
        self.assertIn("净值与回撤", html)
        self.assertIn("候选订单与风控", html)
        self.assertIn("新闻核验", html)
        self.assertIn("清晰分析结论", html)
        self.assertIn("chartData", html)

    def test_write_html_report_creates_file(self):
        data = generate_sample_ohlcv("SAMPLE", periods=60, seed=7)
        signal = moving_average_signal(data, 5, 20)
        backtest = run_backtest(data, signal, BacktestConfig(initial_cash=2_000))
        analysis = analyze_market_data(data, signal, 5, 20)
        news = NewsCheck(items=[], status="empty", message="无新闻", verification_links=[])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "dashboard.html"
            write_html_report(
                path,
                HtmlReportContext(
                    symbol="000001",
                    trade_date="2024-03-29",
                    source="akshare-sina",
                    cache_status="hit",
                    capital_profile="small-2000",
                    cash=2_000,
                    latest_close=10.0,
                    latest_signal=0.0,
                    risk_config=RiskConfig(),
                    order=None,
                    decision=None,
                    backtest=backtest,
                    analysis=analysis,
                    news=news,
                ),
            )

            self.assertTrue(path.exists())
            self.assertIn("<!doctype html>", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
