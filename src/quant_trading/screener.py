from __future__ import annotations

from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from importlib import import_module
import math
import re

import pandas as pd

from quant_trading.news import NewsCheck, fetch_stock_news


@dataclass(frozen=True)
class HotBoard:
    name: str
    pct_change: float
    leader: str
    leader_pct: float


@dataclass(frozen=True)
class Candidate:
    code: str
    name: str
    price: float
    pct_change: float
    turnover_rate: float
    volume_ratio: float
    amount: float
    strategy: str
    score: float
    reasons: list[str]
    sentiment_label: str
    sentiment_score: int
    news: NewsCheck


@dataclass(frozen=True)
class ScreenResult:
    strategy: str
    candidates: list[Candidate]
    hot_boards: list[HotBoard]
    status: str
    message: str


def screen_market(strategy: str = "momentum", limit: int = 10, news_limit: int = 3, quote_timeout: int = 25) -> ScreenResult:
    hot_boards = []
    executor = ThreadPoolExecutor(max_workers=2)
    boards_future = executor.submit(fetch_hot_boards)
    quotes_future = executor.submit(fetch_realtime_quotes)
    try:
        try:
            hot_boards = boards_future.result(timeout=10)
        except Exception:
            hot_boards = []
        try:
            quotes = quotes_future.result(timeout=quote_timeout)
        except TimeoutError as exc:
            quotes_future.cancel()
            raise TimeoutError(f"实时行情接口超过 {quote_timeout} 秒未返回") from exc
    except Exception as exc:
        return ScreenResult(
            strategy=strategy,
            candidates=[],
            hot_boards=hot_boards,
            status="error",
            message=f"实时行情获取失败：{exc}",
        )
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if quotes.empty:
        return ScreenResult(strategy=strategy, candidates=[], hot_boards=hot_boards, status="empty", message="实时行情为空。")

    candidates = []
    for _, row in quotes.iterrows():
        candidate = _evaluate_candidate(row, strategy)
        if candidate is not None:
            candidates.append(candidate)
    candidates = sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]

    enriched = []
    for candidate in candidates:
        news = fetch_stock_news(candidate.code, limit=news_limit)
        sentiment_score, sentiment_label = score_news_sentiment(news)
        enriched.append(
            Candidate(
                code=candidate.code,
                name=candidate.name,
                price=candidate.price,
                pct_change=candidate.pct_change,
                turnover_rate=candidate.turnover_rate,
                volume_ratio=candidate.volume_ratio,
                amount=candidate.amount,
                strategy=candidate.strategy,
                score=candidate.score + sentiment_score * 0.2,
                reasons=candidate.reasons,
                sentiment_label=sentiment_label,
                sentiment_score=sentiment_score,
                news=news,
            )
        )

    return ScreenResult(strategy=strategy, candidates=enriched, hot_boards=hot_boards, status="ok", message="实时扫描完成。")


def fetch_realtime_quotes() -> pd.DataFrame:
    ak = import_module("akshare")
    raw = ak.stock_zh_a_spot_em()
    rename = {
        "代码": "code",
        "名称": "name",
        "最新价": "price",
        "涨跌幅": "pct_change",
        "成交额": "amount",
        "总市值": "market_cap",
        "流通市值": "float_market_cap",
        "换手率": "turnover_rate",
        "量比": "volume_ratio",
        "60日涨跌幅": "return_60d",
        "年初至今涨跌幅": "return_ytd",
    }
    frame = raw.rename(columns=rename).copy()
    required = ["code", "name", "price", "pct_change", "amount", "turnover_rate", "volume_ratio"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"实时行情缺少字段: {missing}")
    for column in [
        "price",
        "pct_change",
        "amount",
        "market_cap",
        "float_market_cap",
        "turnover_rate",
        "volume_ratio",
        "return_60d",
        "return_ytd",
    ]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["price", "pct_change"])
    frame = frame[frame["price"] > 0]
    return frame


def fetch_hot_boards(limit: int = 10) -> list[HotBoard]:
    try:
        ak = import_module("akshare")
        raw = ak.stock_board_industry_name_em()
        rows = raw.head(limit)
        boards = []
        for _, row in rows.iterrows():
            boards.append(
                HotBoard(
                    name=str(row.get("板块名称", "")),
                    pct_change=_number(row.get("涨跌幅", 0.0)),
                    leader=str(row.get("领涨股票", "")),
                    leader_pct=_number(row.get("领涨股票-涨跌幅", 0.0)),
                )
            )
        return boards
    except Exception:
        return []


def score_news_sentiment(news: NewsCheck) -> tuple[int, str]:
    text = " ".join(item.title for item in news.items)
    positive = ["增长", "预增", "中标", "突破", "回购", "增持", "涨停", "创新高", "签约", "盈利"]
    negative = ["亏损", "减持", "处罚", "调查", "下滑", "终止", "风险", "退市", "诉讼", "暴跌"]
    score = sum(text.count(word) for word in positive) - sum(text.count(word) for word in negative)
    if score > 0:
        return score, "偏积极"
    if score < 0:
        return score, "偏谨慎"
    return 0, "中性或待核验"


def _evaluate_candidate(row: pd.Series, strategy: str) -> Candidate | None:
    pct = _number(row.get("pct_change", 0.0))
    turnover = _number(row.get("turnover_rate", 0.0))
    volume_ratio = _number(row.get("volume_ratio", 0.0))
    amount = _number(row.get("amount", 0.0))
    market_cap = _number(row.get("market_cap", 0.0))
    float_market_cap = _number(row.get("float_market_cap", 0.0))
    return_60d = _number(row.get("return_60d", 0.0))
    return_ytd = _number(row.get("return_ytd", 0.0))
    code = str(row.get("code", ""))
    name = str(row.get("name", ""))
    price = _number(row.get("price", 0.0))
    reasons: list[str] = []

    if not re.fullmatch(r"\d{6}", code):
        return None
    if name.startswith(("ST", "*ST")):
        return None

    if strategy == "momentum":
        if pct < 2 or amount < 100_000_000:
            return None
        score = pct * 1.5 + turnover * 0.3 + min(volume_ratio, 5) + max(return_60d, 0) * 0.05
        reasons = [f"当日涨跌幅 {pct:.2f}%", f"成交额 {amount/100_000_000:.2f} 亿", f"量比 {volume_ratio:.2f}"]
    elif strategy == "breakout":
        if pct < 1 or return_60d < 15:
            return None
        score = return_60d * 0.7 + pct + min(volume_ratio, 5)
        reasons = [f"60 日涨跌幅 {return_60d:.2f}%", f"当日继续上涨 {pct:.2f}%", f"量比 {volume_ratio:.2f}"]
    elif strategy == "reversal":
        if pct > -2 or return_ytd > -10:
            return None
        score = abs(pct) + abs(min(return_ytd, 0)) * 0.2 + turnover * 0.2
        reasons = [f"当日回调 {pct:.2f}%", f"年初至今 {return_ytd:.2f}%", "仅作为反转观察，不代表抄底"]
    elif strategy == "overnight_yang":
        effective_cap = float_market_cap or market_cap
        if volume_ratio < 1 or turnover < 5 or turnover > 10 or effective_cap <= 0 or effective_cap > 20_000_000_000 or pct < 1:
            return None
        score = pct * 1.2 + volume_ratio * 2 + (10 - abs(turnover - 7.5)) + max(0, 20_000_000_000 - effective_cap) / 2_000_000_000
        reasons = [
            "杨永兴风格隔夜观察：尾盘候选，非自动买入",
            f"量比 {volume_ratio:.2f}，高于 1",
            f"换手率 {turnover:.2f}%，处于 5%-10% 区间",
            f"参考市值 {effective_cap/100_000_000:.2f} 亿，低于 200 亿",
            f"当日涨幅 {pct:.2f}%，需人工确认分时是否强于均线",
        ]
    else:
        raise ValueError(f"未知策略: {strategy}")

    return Candidate(
        code=code,
        name=name,
        price=price,
        pct_change=pct,
        turnover_rate=turnover,
        volume_ratio=volume_ratio,
        amount=amount,
        strategy=strategy,
        score=score,
        reasons=reasons,
        sentiment_label="待核验",
        sentiment_score=0,
        news=NewsCheck(items=[], status="empty", message="尚未核验新闻。", verification_links=[]),
    )


def _number(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(number) else number
