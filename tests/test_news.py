import sys
import types
import unittest

import pandas as pd

from tests import context  # noqa: F401
from quant_trading.news import fetch_stock_news


class NewsTests(unittest.TestCase):
    def tearDown(self):
        sys.modules.pop("akshare", None)

    def test_fetch_stock_news_normalizes_items(self):
        sys.modules["akshare"] = types.SimpleNamespace(
            stock_news_em=lambda symbol: pd.DataFrame(
                {
                    "新闻标题": ["测试新闻"],
                    "发布时间": ["2026-05-19 10:00:00"],
                    "文章来源": ["东方财富"],
                    "新闻链接": ["https://example.com/news"],
                }
            )
        )

        result = fetch_stock_news("sz000001")

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.items[0].title, "测试新闻")
        self.assertTrue(result.verification_links)

    def test_fetch_stock_news_returns_error_with_links(self):
        sys.modules["akshare"] = types.SimpleNamespace(stock_news_em=lambda symbol: (_ for _ in ()).throw(RuntimeError("down")))

        result = fetch_stock_news("000001")

        self.assertEqual(result.status, "error")
        self.assertTrue(result.verification_links)


if __name__ == "__main__":
    unittest.main()
