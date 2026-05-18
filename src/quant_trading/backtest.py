from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from quant_trading.data import validate_ohlcv
from quant_trading.metrics import PerformanceMetrics, calculate_metrics


@dataclass(frozen=True)
class BacktestConfig:
    initial_cash: float = 100_000.0
    fee_rate: float = 0.0003
    slippage_rate: float = 0.0002


@dataclass(frozen=True)
class BacktestResult:
    equity_curve: pd.DataFrame
    metrics: PerformanceMetrics


def run_backtest(data: pd.DataFrame, signal: pd.Series, config: BacktestConfig | None = None) -> BacktestResult:
    """Run a long-only close-to-close backtest without look-ahead bias."""
    config = config or BacktestConfig()
    if config.initial_cash <= 0:
        raise ValueError("initial_cash must be positive")
    if config.fee_rate < 0 or config.slippage_rate < 0:
        raise ValueError("cost rates must be non-negative")

    validate_ohlcv(data)
    if len(signal) != len(data):
        raise ValueError("signal length must match data length")

    frame = data.copy()
    frame["date"] = pd.to_datetime(frame["date"])
    frame["signal"] = pd.to_numeric(signal.reset_index(drop=True), errors="raise").clip(0, 1)

    frame["asset_return"] = frame["close"].pct_change().fillna(0.0)
    frame["position"] = frame["signal"].shift(1).fillna(0.0)
    frame["turnover"] = frame["position"].diff().abs().fillna(frame["position"].abs())
    cost = frame["turnover"] * (config.fee_rate + config.slippage_rate)
    frame["strategy_return"] = frame["position"] * frame["asset_return"] - cost
    frame["equity"] = config.initial_cash * (1 + frame["strategy_return"]).cumprod()
    frame["drawdown"] = frame["equity"] / frame["equity"].cummax() - 1

    equity_curve = frame[
        ["date", "close", "signal", "position", "asset_return", "strategy_return", "equity", "drawdown"]
    ].copy()
    metrics = calculate_metrics(equity_curve["equity"], equity_curve["strategy_return"])
    return BacktestResult(equity_curve=equity_curve, metrics=metrics)
