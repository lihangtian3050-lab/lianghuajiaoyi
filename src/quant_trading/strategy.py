from __future__ import annotations

import pandas as pd


def moving_average_signal(
    data: pd.DataFrame,
    fast_window: int = 10,
    slow_window: int = 30,
) -> pd.Series:
    """Return 1 when the fast moving average is above the slow average, else 0."""
    if fast_window <= 0 or slow_window <= 0:
        raise ValueError("window sizes must be positive")
    if fast_window >= slow_window:
        raise ValueError("fast_window must be smaller than slow_window")
    if "close" not in data.columns:
        raise ValueError("data must contain close column")

    close = pd.to_numeric(data["close"], errors="raise")
    fast = close.rolling(fast_window, min_periods=fast_window).mean()
    slow = close.rolling(slow_window, min_periods=slow_window).mean()
    signal = (fast > slow).astype(float)
    signal.name = "signal"
    return signal.fillna(0.0)
