from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class PerformanceMetrics:
    total_return: float
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    max_drawdown: float


def calculate_metrics(equity: pd.Series, daily_returns: pd.Series, periods_per_year: int = 252) -> PerformanceMetrics:
    if equity.empty:
        raise ValueError("equity must not be empty")

    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1)
    years = max(len(equity) / periods_per_year, 1 / periods_per_year)
    annual_return = float((1 + total_return) ** (1 / years) - 1)
    annual_volatility = float(daily_returns.std(ddof=0) * np.sqrt(periods_per_year))
    sharpe_ratio = 0.0 if annual_volatility == 0 else float(annual_return / annual_volatility)

    running_max = equity.cummax()
    drawdown = equity / running_max - 1
    max_drawdown = float(drawdown.min())

    return PerformanceMetrics(
        total_return=total_return,
        annual_return=annual_return,
        annual_volatility=annual_volatility,
        sharpe_ratio=sharpe_ratio,
        max_drawdown=max_drawdown,
    )
