import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

from tests import context  # noqa: F401
from quant_trading.news import NewsCheck, NewsItem
from quant_trading.screener import analyze_stock, fetch_hot_boards, fetch_realtime_quotes, screen_market, score_news_sentiment


class ScreenerTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("akshare", None)

    def test_fetch_realtime_quotes_normalizes_columns(self):
        sys.modules["akshare"] = types.SimpleNamespace(
            stock_zh_a_spot_em=lambda: pd.DataFrame(
                {
                    "代码": ["000001"],
                    "名称": ["平安银行"],
                    "最新价": [11.0],
                    "涨跌幅": [2.5],
                    "成交额": [200_000_000],
                    "总市值": [15_000_000_000],
                    "流通市值": [12_000_000_000],
                    "换手率": [2.0],
                    "量比": [1.5],
                    "60日涨跌幅": [20.0],
                    "年初至今涨跌幅": [5.0],
                }
            )
        )

        quotes = fetch_realtime_quotes()

        self.assertEqual(quotes["code"].tolist(), ["000001"])
        self.assertEqual(quotes["pct_change"].tolist(), [2.5])

    def test_fetch_hot_boards(self):
        sys.modules["akshare"] = types.SimpleNamespace(
            stock_board_industry_name_em=lambda: pd.DataFrame(
                {
                    "板块名称": ["半导体"],
                    "涨跌幅": [3.2],
                    "领涨股票": ["测试股份"],
                    "领涨股票-涨跌幅": [10.0],
                }
            )
        )

        boards = fetch_hot_boards()

        self.assertEqual(boards[0].name, "半导体")

    def test_screen_market_returns_momentum_candidate(self):
        quotes = pd.DataFrame(
            {
                "code": ["000001", "000002"],
                "name": ["平安银行", "万科A"],
                "price": [11.0, 8.0],
                "pct_change": [3.2, 0.5],
                "amount": [300_000_000, 50_000_000],
                "market_cap": [15_000_000_000, 250_000_000_000],
                "float_market_cap": [12_000_000_000, 220_000_000_000],
                "turnover_rate": [2.5, 1.0],
                "volume_ratio": [1.8, 0.8],
                "return_60d": [18.0, 2.0],
                "return_ytd": [8.0, -1.0],
            }
        )
        news = NewsCheck(
            items=[NewsItem("公司增长突破", "2026-05-19", "测试", "https://example.com")],
            status="ok",
            message="ok",
            verification_links=[],
        )

        with patch("quant_trading.screener.fetch_realtime_quotes", return_value=quotes), patch(
            "quant_trading.screener.fetch_hot_boards", return_value=[]
        ), patch("quant_trading.screener.fetch_stock_news", return_value=news):
            result = screen_market("momentum", limit=5, quote_timeout=5)

        self.assertEqual(result.status, "ok")
        self.assertTrue(result.research_steps)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].code, "000001")
        self.assertEqual(result.candidates[0].sentiment_label, "偏积极")

    def test_screen_market_returns_overnight_candidate(self):
        quotes = pd.DataFrame(
            {
                "code": ["000001", "000002"],
                "name": ["平安银行", "万科A"],
                "price": [11.0, 8.0],
                "pct_change": [2.2, 2.5],
                "amount": [300_000_000, 300_000_000],
                "market_cap": [15_000_000_000, 300_000_000_000],
                "float_market_cap": [12_000_000_000, 250_000_000_000],
                "turnover_rate": [6.5, 6.0],
                "volume_ratio": [1.8, 1.9],
                "return_60d": [8.0, 10.0],
                "return_ytd": [3.0, 5.0],
            }
        )
        news = NewsCheck(items=[], status="empty", message="待核验", verification_links=[])

        with patch("quant_trading.screener.fetch_realtime_quotes", return_value=quotes), patch(
            "quant_trading.screener.fetch_hot_boards", return_value=[]
        ), patch("quant_trading.screener.fetch_stock_news", return_value=news):
            result = screen_market("overnight_yang", limit=5, quote_timeout=5)

        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].code, "000001")
        self.assertIn("杨永兴风格隔夜观察", result.candidates[0].reasons[0])

    def test_analyze_stock_returns_strategy_matches(self):
        quotes = pd.DataFrame(
            {
                "code": ["000001"],
                "name": ["平安银行"],
                "price": [11.0],
                "pct_change": [2.2],
                "amount": [300_000_000],
                "market_cap": [15_000_000_000],
                "float_market_cap": [12_000_000_000],
                "turnover_rate": [6.5],
                "volume_ratio": [1.8],
                "return_60d": [18.0],
                "return_ytd": [3.0],
            }
        )
        news = NewsCheck(items=[], status="empty", message="待核验", verification_links=[])

        with patch("quant_trading.screener.fetch_realtime_quotes", return_value=quotes), patch("quant_trading.screener.fetch_stock_news", return_value=news):
            result = analyze_stock("000001", quote_timeout=5)

        self.assertEqual(result.symbol, "000001")
        self.assertEqual(result.name, "平安银行")
        self.assertGreaterEqual(len(result.strategy_matches), 1)
        self.assertTrue(result.checklist)

    def test_score_news_sentiment_negative(self):
        news = NewsCheck(
            items=[NewsItem("公司亏损并被调查", "", "", "")],
            status="ok",
            message="",
            verification_links=[],
        )

        score, label = score_news_sentiment(news)

        self.assertLess(score, 0)
        self.assertEqual(label, "偏谨慎")


if __name__ == "__main__":
    unittest.main()
