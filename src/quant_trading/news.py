from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import re

import pandas as pd


@dataclass(frozen=True)
class NewsItem:
    title: str
    publish_time: str
    source: str
    url: str


@dataclass(frozen=True)
class NewsCheck:
    items: list[NewsItem]
    status: str
    message: str
    verification_links: list[tuple[str, str]]


def fetch_stock_news(symbol: str, limit: int = 5) -> NewsCheck:
    code = _strip_market_prefix(symbol)
    links = [
        ("东方财富新闻搜索", f"https://so.eastmoney.com/news/s?keyword={code}"),
        ("百度股市通搜索", f"https://www.baidu.com/s?wd={code}%20股票%20新闻"),
    ]
    try:
        ak = import_module("akshare")
        raw = ak.stock_news_em(symbol=code)
        items = _normalize_news(raw).items[:limit]
        if not items:
            return NewsCheck(
                items=[],
                status="empty",
                message="新闻接口未返回可展示内容，请打开核验链接人工确认。",
                verification_links=links,
            )
        return NewsCheck(
            items=items,
            status="ok",
            message="已从东方财富个股新闻接口获取新闻，仍建议人工打开链接核验原文。",
            verification_links=links,
        )
    except Exception as exc:
        return NewsCheck(
            items=[],
            status="error",
            message=f"新闻接口暂不可用：{exc}。请使用下方链接人工核验最新消息。",
            verification_links=links,
        )


def _normalize_news(raw: pd.DataFrame) -> NewsCheck:
    rename_map = {
        "新闻标题": "title",
        "发布时间": "publish_time",
        "文章来源": "source",
        "新闻链接": "url",
        "标题": "title",
        "时间": "publish_time",
        "来源": "source",
        "链接": "url",
    }
    frame = raw.rename(columns=rename_map).copy()
    for column in ["title", "publish_time", "source", "url"]:
        if column not in frame.columns:
            frame[column] = ""
    items = []
    for _, row in frame.head(20).iterrows():
        title = str(row["title"]).strip()
        if not title:
            continue
        items.append(
            NewsItem(
                title=title,
                publish_time=str(row["publish_time"]).strip(),
                source=str(row["source"]).strip(),
                url=str(row["url"]).strip(),
            )
        )
    return NewsCheck(items=items, status="ok", message="", verification_links=[])


def _strip_market_prefix(symbol: str) -> str:
    normalized = symbol.lower().strip()
    return re.sub(r"^(sh|sz|bj)", "", normalized)
