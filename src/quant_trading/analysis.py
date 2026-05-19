from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class TechnicalAnalysis:
    close: float
    return_20d: float
    return_60d: float
    ma_fast: float
    ma_slow: float
    volatility_20d: float
    high_60d: float
    low_60d: float
    trend_label: str
    signal_label: str
    research_conclusion: str
    risk_notes: list[str]


def analyze_market_data(data: pd.DataFrame, signal: pd.Series, fast_window: int = 10, slow_window: int = 30) -> TechnicalAnalysis:
    if data.empty:
        raise ValueError("data must not be empty")
    close = pd.to_numeric(data["close"], errors="raise")
    returns = close.pct_change()
    latest_close = float(close.iloc[-1])
    ma_fast = float(close.rolling(fast_window, min_periods=1).mean().iloc[-1])
    ma_slow = float(close.rolling(slow_window, min_periods=1).mean().iloc[-1])
    return_20d = _window_return(close, 20)
    return_60d = _window_return(close, 60)
    volatility_20d = float(returns.tail(20).std(ddof=0) * (252**0.5)) if len(returns.dropna()) else 0.0
    high_60d = float(close.tail(60).max())
    low_60d = float(close.tail(60).min())
    latest_signal = float(signal.iloc[-1]) if len(signal) else 0.0

    if ma_fast > ma_slow and return_20d > 0:
        trend_label = "短期偏强"
    elif ma_fast < ma_slow and return_20d < 0:
        trend_label = "短期偏弱"
    else:
        trend_label = "震荡或信号不一致"

    signal_label = "策略观察到持有信号" if latest_signal > 0 else "策略观察到空仓信号"
    risk_notes = []
    if volatility_20d > 0.35:
        risk_notes.append("近 20 日波动较高，仓位应更保守。")
    if latest_close < ma_slow:
        risk_notes.append("价格低于慢均线，趋势确认不足。")
    if return_60d < -0.1:
        risk_notes.append("近 60 日跌幅较大，需要警惕趋势延续。")
    if not risk_notes:
        risk_notes.append("未触发额外技术风险提示，但仍需结合基本面和新闻核验。")

    if latest_signal > 0 and ma_fast > ma_slow:
        conclusion = "规则研究结论：策略条件偏积极，可进入人工复核清单。"
    elif latest_signal <= 0 and ma_fast < ma_slow:
        conclusion = "规则研究结论：策略条件偏谨慎，当前更适合观察或控制仓位。"
    else:
        conclusion = "规则研究结论：信号不够一致，建议等待更清晰的确认。"

    return TechnicalAnalysis(
        close=latest_close,
        return_20d=return_20d,
        return_60d=return_60d,
        ma_fast=ma_fast,
        ma_slow=ma_slow,
        volatility_20d=volatility_20d,
        high_60d=high_60d,
        low_60d=low_60d,
        trend_label=trend_label,
        signal_label=signal_label,
        research_conclusion=conclusion,
        risk_notes=risk_notes,
    )


def _window_return(close: pd.Series, window: int) -> float:
    if len(close) <= window:
        return float(close.iloc[-1] / close.iloc[0] - 1)
    return float(close.iloc[-1] / close.iloc[-window - 1] - 1)
