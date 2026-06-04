import sys
import types
import unittest
from unittest.mock import patch

import pandas as pd

from tests import context  # noqa: F401
from quant_trading.news import NewsCheck, NewsItem
from quant_trading.screener import (
    analyze_stock,
    fetch_hot_boards,
    fetch_realtime_quotes,
    screen_market,
    score_news_sentiment,
)


class ScreenerTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("akshare", None)

    def test_fetch_realtime_quotes_normalizes_eastmoney_columns(self):
        payload = (
            '{"data":{"diff":[{"f12":"000001","f14":"平安银行","f2":11.0,'
            '"f3":2.5,"f6":200000000,"f20":15000000000,"f21":12000000000,'
            '"f8":2.0,"f10":1.5,"f24":20.0,"f25":5.0}]}}'
        )

        with patch("quant_trading.screener._read_url", return_value=payload):
            quotes = fetch_realtime_quotes({"sources": ["eastmoney"]})

        self.assertEqual(quotes.attrs["source"], "东方财富热榜扫描")
        self.assertEqual(quotes["code"].tolist(), ["000001"])
        self.assertEqual(quotes["pct_change"].tolist(), [2.5])

    def test_fetch_realtime_quotes_falls_back_to_tencent(self):
        sys.modules["akshare"] = types.SimpleNamespace(stock_zh_a_spot_em=lambda: (_ for _ in ()).throw(RuntimeError("eastmoney down")))
        payload = (
            'v_sz000001="51~平安银行~000001~10.82~10.99~10.91~869271~318011~551259~10.82~2049~10.81~1679~10.80~4878~10.79~1168~10.78~1883~'
            '10.83~875~10.84~2376~10.85~4214~10.86~1251~10.87~996~~20260604161445~-0.17~-1.55~10.97~10.77~10.82/869271/943329311~'
            '869271~94333~0.45~4.88~~10.97~10.77~1.82~2099.69~2099.72~0.45~12.09~9.89~0.88~1945~10.85~3.61~4.93~~~'
            '0.41~94332.9311~0.0000~0~ ~GP-A~-5.17~1.50~5.53~7.91~0.71~13.09~10.43~1.12~-4.84~0.00~19405600653~19405918198";'
        )

        with patch("quant_trading.screener._read_url", return_value=payload):
            quotes = fetch_realtime_quotes({"watchlist": {"000001": "平安银行"}})

        self.assertEqual(quotes.attrs["source"], "腾讯自选池")
        self.assertEqual(quotes.iloc[0]["name"], "平安银行")
        self.assertAlmostEqual(quotes.iloc[0]["pct_change"], -1.55)
        self.assertGreater(quotes.iloc[0]["market_cap"], 0)

    def test_fetch_realtime_quotes_falls_back_to_sina(self):
        sys.modules["akshare"] = types.SimpleNamespace(stock_zh_a_spot_em=lambda: (_ for _ in ()).throw(RuntimeError("eastmoney down")))
        sina_payload = 'var hq_str_sz000001="平安银行,10.910,10.990,10.820,10.970,10.770,10.820,10.830,86927083,943329311.390,204862,10.820,167930,10.810,487800,10.800,116800,10.790,188300,10.780,87500,10.830,237600,10.840,421400,10.850,2026-06-04,16:14:45,00";'

        def fake_read_url(url, **kwargs):
            if "qt.gtimg.cn" in url:
                raise RuntimeError("tencent down")
            return sina_payload

        with patch("quant_trading.screener._read_url", side_effect=fake_read_url):
            quotes = fetch_realtime_quotes({"watchlist": {"000001": "平安银行"}})

        self.assertEqual(quotes.attrs["source"], "新浪自选池")
        self.assertEqual(quotes.iloc[0]["code"], "000001")
        self.assertGreater(quotes.iloc[0]["amount"], 0)

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
        quotes.attrs["source"] = "测试源"
        news = NewsCheck(items=[NewsItem("公司增长突破", "2026-05-19", "测试", "https://example.com")], status="ok", message="ok", verification_links=[])

        with patch("quant_trading.screener.fetch_realtime_quotes", return_value=quotes), patch("quant_trading.screener.fetch_hot_boards", return_value=[]), patch("quant_trading.screener.fetch_stock_news", return_value=news):
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
        quotes.attrs["source"] = "测试源"
        news = NewsCheck(items=[], status="empty", message="待核验", verification_links=[])

        with patch("quant_trading.screener.fetch_realtime_quotes", return_value=quotes), patch("quant_trading.screener.fetch_hot_boards", return_value=[]), patch("quant_trading.screener.fetch_stock_news", return_value=news):
            result = screen_market("overnight_yang", limit=5, quote_timeout=5)

        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].code, "000001")
        self.assertIn("杨永兴风格隔夜观察", result.candidates[0].reasons[0])

    def test_screen_market_returns_observation_pool_when_strict_strategy_empty(self):
        quotes = pd.DataFrame(
            {
                "code": ["000001", "300059"],
                "name": ["平安银行", "东方财富"],
                "price": [10.82, 18.74],
                "pct_change": [-1.55, -0.90],
                "amount": [943_330_000, 4_205_120_000],
                "market_cap": [209_969_000_000, 250_000_000_000],
                "float_market_cap": [209_972_000_000, 220_000_000_000],
                "turnover_rate": [0.45, 1.68],
                "volume_ratio": [0.88, 0.74],
                "return_60d": [0.0, 0.0],
                "return_ytd": [-5.17, -8.0],
            }
        )
        quotes.attrs["source"] = "腾讯自选池"
        news = NewsCheck(items=[NewsItem("测试新闻", "2026-06-04", "测试", "https://example.com")], status="ok", message="ok", verification_links=[])

        with patch("quant_trading.screener.fetch_realtime_quotes", return_value=quotes), patch("quant_trading.screener.fetch_hot_boards", return_value=[]), patch("quant_trading.screener.fetch_stock_news", return_value=news):
            result = screen_market("overnight_yang", limit=5, quote_timeout=5)

        self.assertEqual(result.status, "ok")
        self.assertEqual(len(result.candidates), 2)
        self.assertIn("实时观察池", result.candidates[0].reasons[0])
        self.assertTrue(any(step.stage == "观察池" for step in result.research_steps))

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
        quotes.attrs["source"] = "测试源"
        news = NewsCheck(items=[], status="empty", message="待核验", verification_links=[])

        with patch("quant_trading.screener.fetch_realtime_quotes", return_value=quotes), patch("quant_trading.screener.fetch_stock_news", return_value=news):
            result = analyze_stock("000001", quote_timeout=5)

        self.assertEqual(result.symbol, "000001")
        self.assertEqual(result.name, "平安银行")
        self.assertGreaterEqual(len(result.strategy_matches), 1)
        self.assertTrue(result.checklist)

    def test_score_news_sentiment_negative(self):
        news = NewsCheck(items=[NewsItem("公司亏损并被调查", "", "", "")], status="ok", message="", verification_links=[])

        score, label = score_news_sentiment(news)

        self.assertLess(score, 0)
        self.assertEqual(label, "偏谨慎")


if __name__ == "__main__":
    unittest.main()
