from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


def generate_sample_ohlcv(symbol: str, periods: int = 260, seed: int = 42) -> pd.DataFrame:
    """Generate deterministic daily OHLCV data for offline tests and demos."""
    if periods <= 0:
        raise ValueError("periods must be positive")

    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2024-01-02", periods=periods)
    daily_returns = rng.normal(loc=0.0004, scale=0.015, size=periods)
    close = 100 * np.cumprod(1 + daily_returns)
    open_ = close * (1 + rng.normal(0, 0.004, size=periods))
    high = np.maximum(open_, close) * (1 + rng.uniform(0.001, 0.015, size=periods))
    low = np.minimum(open_, close) * (1 - rng.uniform(0.001, 0.015, size=periods))
    volume = rng.integers(500_000, 5_000_000, size=periods)

    return pd.DataFrame(
        {
            "date": dates,
            "symbol": symbol,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }
    )


def validate_ohlcv(data: pd.DataFrame) -> None:
    """Validate the minimum assumptions required by the backtest engine."""
    missing = [column for column in REQUIRED_COLUMNS if column not in data.columns]
    if missing:
        raise ValueError(f"missing required columns: {missing}")
    if data.empty:
        raise ValueError("data must not be empty")

    dates = pd.to_datetime(data["date"], errors="coerce")
    if dates.isna().any():
        raise ValueError("date column contains invalid values")
    if dates.duplicated().any():
        raise ValueError("date column contains duplicates")
    if not dates.is_monotonic_increasing:
        raise ValueError("date column must be sorted ascending")

    numeric_columns = ["open", "high", "low", "close", "volume"]
    numeric = data[numeric_columns].apply(pd.to_numeric, errors="coerce")
    if numeric.isna().any().any():
        raise ValueError("price and volume columns must be numeric")
    if (numeric[["open", "high", "low", "close"]] <= 0).any().any():
        raise ValueError("prices must be positive")
    if (numeric["volume"] < 0).any():
        raise ValueError("volume must be non-negative")
    if (numeric["high"] < numeric[["open", "close"]].max(axis=1)).any():
        raise ValueError("high must be at least open and close")
    if (numeric["low"] > numeric[["open", "close"]].min(axis=1)).any():
        raise ValueError("low must be at most open and close")
