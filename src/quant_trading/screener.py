from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass
from importlib import import_module
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import json
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


def screen_market(strategy: str = "momentum", limit: int = 10, news_limit: int = 3, quote_timeout: int = 20) -> ScreenResult:
    steps = [ResearchStep("初始化", "ok", f"使用 {strategy} 策略，目标候选数量 {limit}。")]
    hot_boards: list[HotBoard] = []
    fallback_message = ""
    executor = ThreadPoolExecutor(max_workers=2)
    boards_future = executor.submit(fetch_hot_boards)
    quotes_future = executor.submit(fetch_realtime_quotes)
    try:
        try:
            quotes = quotes_future.result(timeout=quote_timeout)
            source = quotes.attrs.get("source", "未知源")
            errors = quotes.attrs.get("source_errors", [])
            detail = f"通过 {source} 获取到 {len(quotes)} 条实时行情。"
            if errors:
                detail += " 备用前失败源：" + "；".join(errors[:2])
            steps.append(ResearchStep("实时行情", "ok", detail))
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
    strict_count = len(candidates)
    if not candidates and not fallback_message:
        candidates = _build_observation_pool(quotes, strategy, limit)
        steps.append(ResearchStep("观察池", "warn", f"严格策略未命中，展示 {len(candidates)} 个实时观察候选。"))
    if strict_count:
        filter_message = f"严格策略筛出 {strict_count} 个候选，按策略分展示前 {len(candidates)} 个。"
    else:
        filter_message = f"严格策略筛出 0 个候选，当前展示 {len(candidates)} 个观察对象。"
    steps.append(ResearchStep("候选筛选", "ok" if strict_count else "warn", filter_message))

    enriched = _enrich_candidates_with_news(candidates, news_limit, fallback_message)
    steps.append(ResearchStep("新闻与情绪", "ok", f"完成 {len(enriched)} 个候选的新闻核验入口和情绪标签。"))
    status = "fallback" if fallback_message else "ok"
    return ScreenResult(strategy, enriched, hot_boards, status, fallback_message or "实时扫描完成。", steps)


def analyze_stock(symbol: str, news_limit: int = 5, quote_timeout: int = 8) -> StockAnalysis:
    code = _strip_market_prefix(symbol)
    steps = [ResearchStep("初始化", "ok", f"分析股票 {code}。")]
    fallback_message = ""
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fetch_realtime_quotes, {"watchlist": {code: DEFAULT_WATCHLIST.get(code, code)}})
            try:
                quotes = future.result(timeout=quote_timeout)
            except TimeoutError as exc:
                future.cancel()
                raise TimeoutError(f"实时行情接口超过 {quote_timeout} 秒未返回") from exc
        steps.append(ResearchStep("实时行情", "ok", f"通过 {quotes.attrs.get('source', '未知源')} 获取到 {len(quotes)} 条行情。"))
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


def fetch_realtime_quotes(options: dict | None = None) -> pd.DataFrame:
    options = options or {}
    watchlist = options.get("watchlist") or DEFAULT_WATCHLIST
    errors: list[str] = []
    source_map = {
        "tencent": ("腾讯自选池", lambda: _fetch_tencent_quotes(watchlist)),
        "sina": ("新浪自选池", lambda: _fetch_sina_quotes(watchlist)),
        "eastmoney": ("东方财富热榜扫描", lambda: _fetch_eastmoney_quotes()),
    }
    source_order = options.get("sources") or ["eastmoney", "tencent", "sina"]
    for source_key in source_order:
        source_name, fetcher = source_map[source_key]
        try:
            frame = fetcher()
            if frame.empty:
                raise ValueError("返回为空")
            frame.attrs["source"] = source_name
            frame.attrs["source_errors"] = errors.copy()
            return frame
        except Exception as exc:
            errors.append(f"{source_name}: {exc}")
    raise RuntimeError("全部实时行情源失败；" + " | ".join(errors))


def _fetch_eastmoney_quotes() -> pd.DataFrame:
    rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=2) as executor:
        for page_rows in executor.map(_fetch_eastmoney_rank_page, ("1", "0")):
            rows.extend(page_rows)
    if not rows:
        raise ValueError("东方财富热榜返回为空")
    frame = _normalize_quote_frame(pd.DataFrame(rows))
    return frame.drop_duplicates(subset=["code"], keep="first").reset_index(drop=True)


def _fetch_eastmoney_rank_page(sort_order: str, page_size: int = 100) -> list[dict]:
    params = {
        "pn": "1",
        "pz": str(page_size),
        "po": sort_order,
        "np": "1",
        "ut": "bd1d9ddb04089700cf9c27f6f7426281",
        "fltt": "2",
        "invt": "2",
        "fid": "f3",
        "fs": "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23,m:0+t:81+s:2048",
        "fields": "f2,f3,f6,f8,f10,f12,f14,f20,f21,f23,f24,f25",
    }
    url = "http://82.push2.eastmoney.com/api/qt/clist/get?" + urlencode(params)
    payload = _read_url(url, encoding="utf-8", headers={"Referer": "http://quote.eastmoney.com/center/gridlist.html"})
    data = json.loads(payload)
    diff = data.get("data", {}).get("diff", []) or []
    rows = []
    for item in diff:
        rows.append(
            {
                "code": item.get("f12", ""),
                "name": item.get("f14", ""),
                "price": _number(item.get("f2", 0.0)),
                "pct_change": _number(item.get("f3", 0.0)),
                "amount": _number(item.get("f6", 0.0)),
                "turnover_rate": _number(item.get("f8", 0.0)),
                "volume_ratio": _number(item.get("f10", 0.0)),
                "market_cap": _number(item.get("f20", 0.0)),
                "float_market_cap": _number(item.get("f21", 0.0)),
                "return_60d": _number(item.get("f24", 0.0)),
                "return_ytd": _number(item.get("f25", 0.0)),
            }
        )
    return rows


def _fetch_tencent_quotes(watchlist: dict[str, str]) -> pd.DataFrame:
    symbols = ",".join(_with_market_prefix(code) for code in watchlist)
    text = _read_url(f"http://qt.gtimg.cn/q={symbols}", encoding="gbk")
    rows = []
    for payload in re.findall(r'v_[a-z]{2}\d{6}="([^"]*)"', text):
        parts = payload.split("~")
        if len(parts) < 74:
            continue
        code = parts[2].strip()
        prev_close = _number(parts[4])
        price = _number(parts[3])
        pct_change = _number(parts[32])
        if pct_change == 0 and prev_close:
            pct_change = (price - prev_close) / prev_close * 100
        rows.append(
            {
                "code": code,
                "name": parts[1].strip() or watchlist.get(code, code),
                "price": price,
                "pct_change": pct_change,
                "amount": _number(parts[37]) * 10_000,
                "turnover_rate": _number(parts[38]),
                "volume_ratio": _number(parts[49]),
                "market_cap": _number(parts[44]) * 100_000_000,
                "float_market_cap": _number(parts[45]) * 100_000_000,
                "return_60d": 0.0,
                "return_ytd": _number(parts[62]),
            }
        )
    return _normalize_quote_frame(pd.DataFrame(rows))


def _fetch_sina_quotes(watchlist: dict[str, str]) -> pd.DataFrame:
    symbols = ",".join(_with_market_prefix(code) for code in watchlist)
    url = f"https://hq.sinajs.cn/list={quote(symbols, safe=',')}"
    text = _read_url(url, encoding="gbk", headers={"Referer": "https://finance.sina.com.cn/"})
    rows = []
    for symbol, payload in re.findall(r'var hq_str_([a-z]{2}\d{6})="([^"]*)"', text):
        parts = payload.split(",")
        if len(parts) < 10 or not parts[0]:
            continue
        code = symbol[-6:]
        prev_close = _number(parts[2])
        price = _number(parts[3])
        pct_change = (price - prev_close) / prev_close * 100 if prev_close else 0.0
        rows.append(
            {
                "code": code,
                "name": parts[0].strip() or watchlist.get(code, code),
                "price": price,
                "pct_change": pct_change,
                "amount": _number(parts[9]),
                "turnover_rate": 0.0,
                "volume_ratio": 0.0,
                "market_cap": 0.0,
                "float_market_cap": 0.0,
                "return_60d": 0.0,
                "return_ytd": 0.0,
            }
        )
    return _normalize_quote_frame(pd.DataFrame(rows))


def _normalize_quote_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = ["code", "name", "price", "pct_change", "amount", "turnover_rate", "volume_ratio"]
    for column in required:
        if column not in frame.columns:
            frame[column] = 0.0 if column not in ("code", "name") else ""
    for column in ["price", "pct_change", "amount", "market_cap", "float_market_cap", "turnover_rate", "volume_ratio", "return_60d", "return_ytd"]:
        if column not in frame.columns:
            frame[column] = 0.0
        frame[column] = pd.to_numeric(frame[column], errors="coerce").fillna(0.0)
    frame["code"] = frame["code"].astype(str).str.extract(r"(\d{6})", expand=False).fillna("")
    frame["name"] = frame["name"].astype(str)
    frame = frame.dropna(subset=["price", "pct_change"])
    return frame[(frame["code"] != "") & (frame["price"] > 0)].reset_index(drop=True)


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
    frame = pd.DataFrame(rows)
    frame.attrs["source"] = "降级候选池"
    return frame


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


def _build_observation_pool(quotes: pd.DataFrame, strategy: str, limit: int) -> list[Candidate]:
    observations = []
    for _, row in quotes.iterrows():
        candidate = _evaluate_observation_candidate(row, strategy)
        if candidate is not None:
            observations.append(candidate)
    return sorted(observations, key=lambda item: item.score, reverse=True)[:limit]


def _enrich_candidates_with_news(candidates: list[Candidate], news_limit: int, fallback_message: str) -> list[Candidate]:
    if not candidates:
        return []
    if fallback_message:
        return [_with_news(candidate, _manual_news_links(candidate.code), 0, "中性或待核验") for candidate in candidates]

    def enrich(candidate: Candidate) -> Candidate:
        news = fetch_stock_news(candidate.code, limit=news_limit)
        sentiment_score, sentiment_label = score_news_sentiment(news)
        return _with_news(candidate, news, sentiment_score, sentiment_label)

    with ThreadPoolExecutor(max_workers=min(6, len(candidates))) as executor:
        return list(executor.map(enrich, candidates))


def _evaluate_observation_candidate(row: pd.Series, strategy: str) -> Candidate | None:
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
        score = pct * 1.2 + min(volume_ratio, 5) + amount / 100_000_000 * 0.08
        reasons = [
            "实时观察池：未命中严格动量条件，先用于盯盘排序",
            f"当日涨跌幅 {pct:.2f}%",
            f"成交额 {amount/100_000_000:.2f} 亿",
            f"量比 {volume_ratio:.2f}",
        ]
    elif strategy == "breakout":
        score = return_60d * 0.4 + pct + min(volume_ratio, 5)
        reasons = [
            "实时观察池：未命中严格突破条件，先用于盯盘排序",
            f"60 日涨跌幅 {return_60d:.2f}%",
            f"当日涨跌幅 {pct:.2f}%",
            f"量比 {volume_ratio:.2f}",
        ]
    elif strategy == "reversal":
        score = abs(min(pct, 0)) + abs(min(return_ytd, 0)) * 0.2 + turnover * 0.15
        reasons = [
            "实时观察池：未命中严格反转条件，先用于盯盘排序",
            f"当日涨跌幅 {pct:.2f}%",
            f"年初至今 {return_ytd:.2f}%",
            f"换手率 {turnover:.2f}%",
        ]
    elif strategy == "overnight_yang":
        effective_cap = float_market_cap or market_cap
        cap_score = max(0, 20_000_000_000 - effective_cap) / 2_000_000_000 if effective_cap else 0
        turnover_score = max(0, 10 - abs(turnover - 7.5)) if turnover else 0
        score = max(pct, -5) * 0.8 + volume_ratio * 2 + turnover_score + cap_score
        reasons = [
            "实时观察池：未命中严格一夜持股条件，先用于盯盘观察",
            f"涨幅 {pct:.2f}%（严格条件需大于 1%）",
            f"量比 {volume_ratio:.2f}（严格条件需大于 1）",
            f"换手率 {turnover:.2f}%（严格条件需 5%-10%）",
        ]
        if effective_cap:
            reasons.append(f"参考市值 {effective_cap/100_000_000:.2f} 亿（严格条件需低于 200 亿）")
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
    return Candidate(candidate.code, candidate.name, candidate.price, candidate.pct_change, candidate.turnover_rate, candidate.volume_ratio, candidate.amount, candidate.strategy, candidate.score, [reason, *candidate.reasons], candidate.sentiment_label, candidate.sentiment_score, candidate.news)


def _with_news(candidate: Candidate, news: NewsCheck, sentiment_score: int, sentiment_label: str) -> Candidate:
    return Candidate(candidate.code, candidate.name, candidate.price, candidate.pct_change, candidate.turnover_rate, candidate.volume_ratio, candidate.amount, candidate.strategy, candidate.score + sentiment_score * 0.2, candidate.reasons, sentiment_label, sentiment_score, news)


def _read_url(url: str, encoding: str = "utf-8", headers: dict[str, str] | None = None) -> str:
    request_headers = {"User-Agent": "Mozilla/5.0"}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    return urlopen(request, timeout=10).read().decode(encoding, errors="ignore")


def _strip_market_prefix(symbol: str) -> str:
    normalized = symbol.lower().strip()
    normalized = re.sub(r"^(sh|sz|bj)", "", normalized)
    return normalized.zfill(6) if normalized.isdigit() else normalized


def _with_market_prefix(symbol: str) -> str:
    code = _strip_market_prefix(symbol)
    if code.startswith(("5", "6", "9")):
        return f"sh{code}"
    if code.startswith(("0", "1", "2", "3")):
        return f"sz{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    raise ValueError(f"无法判断市场前缀: {symbol}")


def _number(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(number) else number
