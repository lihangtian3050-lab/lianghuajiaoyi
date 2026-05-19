from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from contextlib import closing
from pathlib import Path
import sqlite3

import pandas as pd

from quant_trading.data import validate_ohlcv
from quant_trading.data_sources import DataSourceConfig, fetch_a_share_history


@dataclass(frozen=True)
class CacheKey:
    symbol: str
    start_date: str
    end_date: str
    source: str
    adjust: str

    @property
    def id(self) -> str:
        return "|".join([self.symbol, self.start_date, self.end_date, self.source, self.adjust])


def get_or_fetch_a_share_history(
    symbol: str,
    start_date: str,
    end_date: str,
    cache_path: str | Path,
    config: DataSourceConfig | None = None,
    refresh: bool = False,
) -> pd.DataFrame:
    config = config or DataSourceConfig()
    key = CacheKey(
        symbol=symbol.strip().lower(),
        start_date=_compact_date(start_date),
        end_date=_compact_date(end_date),
        source=config.source.lower(),
        adjust=config.adjust,
    )

    path = Path(cache_path)
    if not refresh:
        cached = load_cached_history(path, key)
        if cached is not None:
            cached.attrs["cache_status"] = "hit"
            return cached

    data = fetch_a_share_history(symbol, start_date, end_date, config)
    save_cached_history(path, key, data)
    data.attrs["cache_status"] = "refreshed"
    return data


def load_cached_history(cache_path: str | Path, key: CacheKey) -> pd.DataFrame | None:
    path = Path(cache_path)
    if not path.exists():
        return None

    with closing(sqlite3.connect(path)) as conn:
        _init_cache(conn)
        meta = conn.execute("select actual_source from metadata where cache_key = ?", (key.id,)).fetchone()
        if meta is None:
            return None
        data = pd.read_sql_query(
            """
            select date, symbol, open, high, low, close, volume
            from prices
            where cache_key = ?
            order by date
            """,
            conn,
            params=(key.id,),
            parse_dates=["date"],
        )

    if data.empty:
        return None

    validate_ohlcv(data)
    data.attrs["source"] = meta[0]
    data.attrs["cache_key"] = key.id
    return data


def save_cached_history(cache_path: str | Path, key: CacheKey, data: pd.DataFrame) -> None:
    validate_ohlcv(data)
    path = Path(cache_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    frame = data[["date", "symbol", "open", "high", "low", "close", "volume"]].copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m-%d")
    frame.insert(0, "cache_key", key.id)

    with closing(sqlite3.connect(path)) as conn:
        _init_cache(conn)
        with conn:
            conn.execute("delete from prices where cache_key = ?", (key.id,))
            frame.to_sql("prices", conn, if_exists="append", index=False)
            conn.execute(
                """
                insert or replace into metadata (
                    cache_key, symbol, start_date, end_date, requested_source,
                    actual_source, adjust, rows, fetched_at
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    key.id,
                    key.symbol,
                    key.start_date,
                    key.end_date,
                    key.source,
                    data.attrs.get("source", key.source),
                    key.adjust,
                    len(frame),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )


def _init_cache(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        create table if not exists metadata (
            cache_key text primary key,
            symbol text not null,
            start_date text not null,
            end_date text not null,
            requested_source text not null,
            actual_source text not null,
            adjust text not null,
            rows integer not null,
            fetched_at text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists prices (
            cache_key text not null,
            date text not null,
            symbol text not null,
            open real not null,
            high real not null,
            low real not null,
            close real not null,
            volume real not null,
            primary key (cache_key, date)
        )
        """
    )


def _compact_date(value: str) -> str:
    compact = "".join(ch for ch in value if ch.isdigit())
    if len(compact) != 8:
        raise ValueError("date must be YYYYMMDD or YYYY-MM-DD")
    return compact
