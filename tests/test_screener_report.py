import unittest

from tests import context  # noqa: F401
from quant_trading.news import NewsCheck
from quant_trading.research_log import ResearchStep
from quant_trading.screener import Candidate, HotBoard, ScreenResult
from quant_trading.screener_report import render_screener_html


class ScreenerReportTests(unittest.TestCase):
    def test_render_screener_html_contains_sections(self):
        result = ScreenResult(
            strategy="overnight_yang",
            hot_boards=[HotBoard("半导体", 3.2, "测试股份", 10.0)],
            candidates=[
                Candidate(
                    code="000001",
                    name="平安银行",
                    price=11.0,
                    pct_change=3.2,
                    turnover_rate=2.5,
                    volume_ratio=1.8,
                    amount=300_000_000,
                    strategy="momentum",
                    score=10.0,
                    reasons=["当日涨跌幅 3.20%"],
                    sentiment_label="偏积极",
                    sentiment_score=1,
                    news=NewsCheck(items=[], status="empty", message="新闻待核验", verification_links=[]),
                )
            ],
            status="ok",
            message="ok",
            research_steps=[ResearchStep("测试", "ok", "流程记录")],
        )

        html = render_screener_html(result, refresh_seconds=0)

        self.assertIn("实时盯盘选股", html)
        self.assertIn("热门板块", html)
        self.assertIn("研究流程", html)
        self.assertIn("平安银行", html)
        self.assertIn("偏积极", html)
        self.assertIn("一夜持股观察", html)


if __name__ == "__main__":
    unittest.main()
