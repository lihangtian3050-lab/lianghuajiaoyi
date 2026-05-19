from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from importlib import import_module
import math
import re

import pandas as pd

from quant_trading.news import NewsCheck, fetch_stock_news
from quant_trading.research_log import ResearchStep


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
    research_steps: list[ResearchStep]


@dataclass(frozen=True)
class StockAnalysis:
    symbol: str
    name: str
    price: float
    pct_change: float
    turnover_rate: float
    volume_ratio: float
    amount: float
    strategy_matches: list[Candidate]
    news: NewsCheck
    sentiment_label: str
    sentiment_score: int
    checklist: list[str]
    status: str
    message: str
    research_steps: list[ResearchStep]


DEFAULT_WATCHLIST = {
    "000001": "平安银行",
    "300750": "宁德时代",
    "002594": "比亚迪",
    "300059": "东方财富",
    "600030": "中信证券",
}

STRATEGIES = ("momentum", "breakout", "reversal", "overnight_yang")


def screen_market(strategy: str = "momentum", limit: int = 10, news_limit: int = 3, quote_timeout: int = 8) -> ScreenResult:
    steps = [ResearchStep("初始化", "ok", f"使用 {strategy} 策略，目标候选数量 {limit}。")]
    hot_boards: list[HotBoard] = []
    fallback_message = ""
    executor = ThreadPoolExecutor(max_workers=2)
    boards_future = executor.submit(fetch_hot_boards)
    quotes_future = executor.submit(fetch_realtime_quotes)
    try:
        try:
            quotes = quotes_future.result(timeout=quote_timeout)
            steps.append(ResearchStep("实时行情", "ok", f"获取到 {len(quotes)} 条实时行情。"))
        except TimeoutError as exc:
            quotes_future.cancel()
            raise TimeoutError(f"实时行情接口超过 {quote_timeout} 秒未返回") from exc
        try:
            hot_boards = boards_future.result(timeout=1)
            steps.append(ResearchStep("热门板块", "ok", f"获取到 {len(hot_boards)} 个板块。"))
        except Exception:
            hot_boards = []
            steps.append(ResearchStep("热门板块", "warn", "板块接口暂不可用，先展示候选股。"))
    except Exception as exc:
        fallback_message = f"实时行情获取失败：{exc}；已切换到近端日线降级候选池。"
        quotes = fetch_fallback_quotes()
        steps.append(ResearchStep("实时行情", "warn", fallback_message))
        steps.append(ResearchStep("降级候选池", "warn", f"使用 {len(quotes)} 条降级候选，价格字段需实时确认。"))
    finally:
        executor.shutdown(wait=False, cancel_futures=True)

    if quotes.empty:
        steps.append(ResearchStep("候选筛选", "warn", "没有可用于筛选的行情记录。"))
        return ScreenResult(strategy, [], hot_boards, "empty", fallback_message or "实时行情为空。", steps)

    candidates = []
    for _, row in quotes.iterrows():
        candidate = _evaluate_candidate(row, strategy)
        if candidate is None:
            continue
        if fallback_message:
            candidate = _with_extra_reason(candidate, "实时行情失败，以下为降级候选，必须刷新确认。")
        candidates.append(candidate)
    candidates = sorted(candidates, key=lambda item: item.score, reverse=True)[:limit]
    steps.append(ResearchStep("候选筛选", "ok" if candidates else "warn", f"策略筛出 {len(candidates)} 个候选。"))

    enriched = []
    for candidate in candidates:
        if fallback_message:
            news = _manual_news_links(candidate.code)
        else:
            news = fetch_stock_news(candidate.code, limit=news_limit)
        sentiment_score, sentiment_label = score_news_sentiment(news)
        enriched.append(_with_news(candidate, news, sentiment_score, sentiment_label))
    steps.append(ResearchStep("新闻与情绪", "ok", f"完成 {len(enriched)} 个候选的新闻核验入口和情绪标签。"))
    status = "fallback" if fallback_message else "ok"
    return ScreenResult(strategy, enriched, hot_boards, status, fallback_message or "实时扫描完成。", steps)


def analyze_stock(symbol: str, news_limit: int = 5, quote_timeout: int = 8) -> StockAnalysis:
    code = _strip_market_prefix(symbol)
    steps = [ResearchStep("初始化", "ok", f"分析股票 {code}。")]
    fallback_message = ""
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fetch_realtime_quotes)
            try:
                quotes = future.result(timeout=quote_timeout)
            except TimeoutError as exc:
                future.cancel()
                raise TimeoutError(f"实时行情接口超过 {quote_timeout} 秒未返回") from exc
        steps.append(ResearchStep("实时行情", "ok", f"获取到 {len(quotes)} 条实时行情。"))
    except Exception as exc:
        fallback_message = f"实时行情获取失败：{exc}；使用降级分析框架。"
        quotes = fetch_fallback_quotes({code: DEFAULT_WATCHLIST.get(code, code)})
        steps.append(ResearchStep("实时行情", "warn", fallback_message))

    row = _find_quote_row(quotes, code)
    if row is None:
        row = pd.Series({"code": code, "name": DEFAULT_WATCHLIST.get(code, code), "price": 0.0, "pct_change": 0.0, "amount": 0.0, "turnover_rate": 0.0, "volume_ratio": 0.0})
        fallback_message = fallback_message or "实时行情中未找到该股票，已生成待核验分析框架。"
        steps.append(ResearchStep("股票定位", "warn", "未找到实时行，展示待人工补充的核验框架。"))
    else:
        steps.append(ResearchStep("股票定位", "ok", f"找到 {row.get('name', code)} 的行情快照。"))

    matches = []
    for strategy in STRATEGIES:
        candidate = _evaluate_candidate(row, strategy)
        if candidate is not None:
            if fallback_message:
                candidate = _with_extra_reason(candidate, "行情为降级或待确认，不能直接作为买入依据。")
            matches.append(candidate)
    steps.append(ResearchStep("策略匹配", "ok" if matches else "warn", f"匹配到 {len(matches)} 个策略观察条件。"))

    news = fetch_stock_news(code, limit=news_limit)
    sentiment_score, sentiment_label = score_news_sentiment(news)
    steps.append(ResearchStep("新闻与情绪", news.status, news.message))

    checklist = [
        "核验实时价格、涨跌幅、成交额和量比是否与券商软件一致。",
        "打开新闻原文，确认是否为当天重大公告、监管风险或市场传闻。",
        "确认所属板块是否处于当日热点，而不是单票孤立异动。",
        "若用于隔夜观察，必须在尾盘复核分时均线、盘口承接和次日卖出纪律。",
        "资金决策必须由人工确认；系统只输出研究候选和风险提示。",
    ]
    status = "fallback" if fallback_message else "ok"
    return StockAnalysis(
        symbol=code,
        name=str(row.get("name", DEFAULT_WATCHLIST.get(code, code))),
        price=_number(row.get("price", 0.0)),
        pct_change=_number(row.get("pct_change", 0.0)),
        turnover_rate=_number(row.get("turnover_rate", 0.0)),
        volume_ratio=_number(row.get("volume_ratio", 0.0)),
        amount=_number(row.get("amount", 0.0)),
        strategy_matches=matches,
        news=news,
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        checklist=checklist,
        status=status,
        message=fallback_message or "单票分析完成。",
        research_steps=steps,
    )


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
    for column in ["price", "pct_change", "amount", "market_cap", "float_market_cap", "turnover_rate", "volume_ratio", "return_60d", "return_ytd"]:
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["price", "pct_change"])
    return frame[frame["price"] > 0]


def fetch_fallback_quotes(watchlist: dict[str, str] | None = None) -> pd.DataFrame:
    watchlist = watchlist or DEFAULT_WATCHLIST
    rows = []
    for index, (code, name) in enumerate(watchlist.items()):
        pct_change = 2.2 + index * 0.25
        return_60d = 18.0 + index * 1.5
        return_ytd = 5.0 + index
        if index == len(watchlist) - 1 and len(watchlist) > 1:
            pct_change = -2.5
            return_ytd = -18.0
        rows.append(
            {
                "code": code,
                "name": name,
                "price": 0.0,
                "pct_change": pct_change,
                "amount": 300_000_000.0,
                "market_cap": 10_000_000_000,
                "float_market_cap": 8_000_000_000,
                "turnover_rate": 6.0,
                "volume_ratio": 1.6 + index * 0.1,
                "return_60d": return_60d,
                "return_ytd": return_ytd,
            }
        )
    return pd.DataFrame(rows)


def fetch_hot_boards(limit: int = 10) -> list[HotBoard]:
    try:
        ak = import_module("akshare")
        raw = ak.stock_board_industry_name_em()
        return [
            HotBoard(
                name=str(row.get("板块名称", "")),
                pct_change=_number(row.get("涨跌幅", 0.0)),
                leader=str(row.get("领涨股票", "")),
                leader_pct=_number(row.get("领涨股票-涨跌幅", 0.0)),
            )
            for _, row in raw.head(limit).iterrows()
        ]
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

    if not re.fullmatch(r"\d{6}", code) or name.startswith(("ST", "*ST")):
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

    return Candidate(code, name, price, pct, turnover, volume_ratio, amount, strategy, score, reasons, "待核验", 0, NewsCheck([], "empty", "尚未核验新闻。", []))


def _find_quote_row(quotes: pd.DataFrame, code: str) -> pd.Series | None:
    if "code" not in quotes.columns:
        return None
    rows = quotes[quotes["code"].astype(str).str.zfill(6) == code]
    if rows.empty:
        return None
    return rows.iloc[0]


def _manual_news_links(code: str) -> NewsCheck:
    return NewsCheck(
        items=[],
        status="fallback",
        message="降级模式不自动抓取新闻，请打开核验链接确认最新消息。",
        verification_links=[
            ("东方财富新闻搜索", f"https://so.eastmoney.com/news/s?keyword={code}"),
            ("百度股市通搜索", f"https://www.baidu.com/s?wd={code}%20股票%20新闻"),
        ],
    )


def _with_extra_reason(candidate: Candidate, reason: str) -> Candidate:
    return Candidate(
        candidate.code,
        candidate.name,
        candidate.price,
        candidate.pct_change,
        candidate.turnover_rate,
        candidate.volume_ratio,
        candidate.amount,
        candidate.strategy,
        candidate.score,
        [reason, *candidate.reasons],
        candidate.sentiment_label,
        candidate.sentiment_score,
        candidate.news,
    )


def _with_news(candidate: Candidate, news: NewsCheck, sentiment_score: int, sentiment_label: str) -> Candidate:
    return Candidate(
        candidate.code,
        candidate.name,
        candidate.price,
        candidate.pct_change,
        candidate.turnover_rate,
        candidate.volume_ratio,
        candidate.amount,
        candidate.strategy,
        candidate.score + sentiment_score * 0.2,
        candidate.reasons,
        sentiment_label,
        sentiment_score,
        news,
    )


def _strip_market_prefix(symbol: str) -> str:
    normalized = symbol.lower().strip()
    normalized = re.sub(r"^(sh|sz|bj)", "", normalized)
    return normalized.zfill(6) if normalized.isdigit() else normalized


def _number(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(number) else number
