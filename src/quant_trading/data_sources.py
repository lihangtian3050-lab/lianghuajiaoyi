from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
import re

import pandas as pd

from quant_trading.data import validate_ohlcv


@dataclass(frozen=True)
class DataSourceConfig:
    source: str = "auto"
    adjust: str = "qfq"
    timeout: float | None = 15


def fetch_a_share_history(
    symbol: str,
    start_date: str,
    end_date: str,
    config: DataSourceConfig | None = None,
) -> pd.DataFrame:
    """Fetch A-share daily history and normalize it to the internal OHLCV schema."""
    config = config or DataSourceConfig()
    source = config.source.lower()

    if source == "auto":
        raw = _fetch_first_available(symbol, start_date, end_date, config)
    elif source == "akshare-eastmoney":
        raw = _fetch_akshare_eastmoney(symbol, start_date, end_date, config)
    elif source == "akshare-sina":
        raw = _fetch_akshare_sina(symbol, start_date, end_date, config)
    elif source == "akshare-tencent":
        raw = _fetch_akshare_tencent(symbol, start_date, end_date, config)
    else:
        raise ValueError(f"unsupported data source: {config.source}")

    normalized = _normalize_akshare_daily(raw, symbol)
    normalized.attrs["source"] = raw.attrs.get("source", source)
    validate_ohlcv(normalized)
    return normalized


def _fetch_first_available(
    symbol: str,
    start_date: str,
    end_date: str,
    config: DataSourceConfig,
) -> pd.DataFrame:
    errors: list[str] = []
    for source in ["akshare-eastmoney", "akshare-sina", "akshare-tencent"]:
        try:
            fallback_config = DataSourceConfig(source=source, adjust=config.adjust, timeout=config.timeout)
            if source == "akshare-eastmoney":
                raw = _fetch_akshare_eastmoney(symbol, start_date, end_date, fallback_config)
                raw.attrs["source"] = source
                return raw
            if source == "akshare-sina":
                raw = _fetch_akshare_sina(symbol, start_date, end_date, fallback_config)
                raw.attrs["source"] = source
                return raw
            raw = _fetch_akshare_tencent(symbol, start_date, end_date, fallback_config)
            raw.attrs["source"] = source
            return raw
        except Exception as exc:
            errors.append(f"{source}: {exc}")
    raise RuntimeError("all data sources failed; " + " | ".join(errors))


def _fetch_akshare_eastmoney(
    symbol: str,
    start_date: str,
    end_date: str,
    config: DataSourceConfig,
) -> pd.DataFrame:
    ak = _load_akshare()
    return ak.stock_zh_a_hist(
        symbol=_strip_market_prefix(symbol),
        period="daily",
        start_date=_compact_date(start_date),
        end_date=_compact_date(end_date),
        adjust=config.adjust,
        timeout=config.timeout,
    )


def _fetch_akshare_sina(
    symbol: str,
    start_date: str,
    end_date: str,
    config: DataSourceConfig,
) -> pd.DataFrame:
    ak = _load_akshare()
    return ak.stock_zh_a_daily(
        symbol=_with_market_prefix(symbol),
        start_date=_compact_date(start_date),
        end_date=_compact_date(end_date),
        adjust=config.adjust,
    )


def _fetch_akshare_tencent(
    symbol: str,
    start_date: str,
    end_date: str,
    config: DataSourceConfig,
) -> pd.DataFrame:
    ak = _load_akshare()
    return ak.stock_zh_a_hist_tx(
        symbol=_with_market_prefix(symbol),
        start_date=_compact_date(start_date),
        end_date=_compact_date(end_date),
        adjust=config.adjust,
        timeout=config.timeout,
    )


def _normalize_akshare_daily(raw: pd.DataFrame, requested_symbol: str) -> pd.DataFrame:
    rename_map = {
        "日期": "date",
        "股票代码": "symbol",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "收盘": "close",
        "成交量": "volume",
    }
    frame = raw.rename(columns=rename_map).copy()
    if "volume" not in frame.columns and "amount" in frame.columns:
        frame = frame.rename(columns={"amount": "volume"})
    if "symbol" not in frame.columns:
        frame["symbol"] = _strip_market_prefix(requested_symbol)

    columns = ["date", "symbol", "open", "high", "low", "close", "volume"]
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"data source response missing columns: {missing}")

    frame = frame[columns]
    frame["date"] = pd.to_datetime(frame["date"])
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="raise")
    normalized = frame.sort_values("date").reset_index(drop=True)
    normalized.attrs.update(raw.attrs)
    return normalized


def _load_akshare():
    try:
        return import_module("akshare")
    except ImportError as exc:
        raise RuntimeError("缺少 akshare，请先运行: python -m pip install -r requirements.txt") from exc


def _compact_date(value: str) -> str:
    compact = re.sub(r"[^0-9]", "", value)
    if len(compact) != 8:
        raise ValueError("date must be YYYYMMDD or YYYY-MM-DD")
    return compact


def _strip_market_prefix(symbol: str) -> str:
    normalized = symbol.lower().strip()
    if normalized.startswith(("sh", "sz", "bj")):
        return normalized[2:]
    return normalized


def _with_market_prefix(symbol: str) -> str:
    normalized = symbol.lower().strip()
    if normalized.startswith(("sh", "sz", "bj")):
        return normalized
    code = _strip_market_prefix(normalized)
    if code.startswith(("5", "6", "9")):
        return f"sh{code}"
    if code.startswith(("0", "1", "2", "3")):
        return f"sz{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    raise ValueError(f"cannot infer market prefix for symbol: {symbol}")
