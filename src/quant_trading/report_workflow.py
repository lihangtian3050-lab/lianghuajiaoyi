from __future__ import annotations

from pathlib import Path

from quant_trading.backtest import BacktestConfig, run_backtest
from quant_trading.data_cache import get_or_fetch_a_share_history
from quant_trading.data_sources import DataSourceConfig
from quant_trading.html_report import HtmlReportContext, write_html_report
from quant_trading.risk import check_order_risk, risk_config_for_profile
from quant_trading.strategy import moving_average_signal
from quant_trading.trading import PaperBroker, build_target_order, round_down_to_lot


def build_html_report_context(
    symbol: str,
    start_date: str,
    end_date: str,
    source: str,
    adjust: str,
    cache_path: str | Path,
    capital_profile: str,
    cash: float | None = None,
    current_position: int = 0,
    refresh: bool = False,
) -> HtmlReportContext:
    profile_cash, risk_config = risk_config_for_profile(capital_profile)
    account_cash = cash if cash is not None else profile_cash
    data = get_or_fetch_a_share_history(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        cache_path=cache_path,
        config=DataSourceConfig(source=source, adjust=adjust),
        refresh=refresh,
    )
    signal = moving_average_signal(data, fast_window=10, slow_window=30)
    backtest = run_backtest(data, signal, BacktestConfig(initial_cash=account_cash))
    latest_signal = float(signal.iloc[-1])
    latest_close = float(data["close"].iloc[-1])

    broker = PaperBroker(cash=account_cash)
    if current_position > 0:
        broker._increase_position(symbol, current_position, latest_close)

    if latest_signal > 0:
        target_value = min(risk_config.max_order_value, risk_config.max_position_value, account_cash - risk_config.min_cash_buffer)
        target_quantity = round_down_to_lot(int(target_value / latest_close), risk_config.lot_size)
        reason = "moving_average_signal=1"
    else:
        target_quantity = 0
        reason = "moving_average_signal=0"

    order = build_target_order(symbol, broker.position_quantity(symbol), target_quantity, latest_close, reason)
    decision = None
    if order is not None:
        decision = check_order_risk(order, broker.cash, broker.positions, {symbol: latest_close}, risk_config)

    return HtmlReportContext(
        symbol=symbol,
        trade_date=str(data["date"].iloc[-1].date()),
        source=data.attrs.get("source", source),
        cache_status=data.attrs.get("cache_status", "disabled"),
        capital_profile=capital_profile,
        cash=account_cash,
        latest_close=latest_close,
        latest_signal=latest_signal,
        risk_config=risk_config,
        order=order,
        decision=decision,
        backtest=backtest,
    )


def generate_html_report(
    output_path: str | Path,
    symbol: str,
    start_date: str,
    end_date: str,
    source: str,
    adjust: str,
    cache_path: str | Path,
    capital_profile: str,
    cash: float | None = None,
    current_position: int = 0,
    refresh: bool = False,
) -> HtmlReportContext:
    context = build_html_report_context(
        symbol=symbol,
        start_date=start_date,
        end_date=end_date,
        source=source,
        adjust=adjust,
        cache_path=cache_path,
        capital_profile=capital_profile,
        cash=cash,
        current_position=current_position,
        refresh=refresh,
    )
    write_html_report(output_path, context)
    return context
