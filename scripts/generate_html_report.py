from argparse import ArgumentParser
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_trading.backtest import BacktestConfig, run_backtest
from quant_trading.data_cache import get_or_fetch_a_share_history
from quant_trading.data_sources import DataSourceConfig
from quant_trading.html_report import HtmlReportContext, write_html_report
from quant_trading.risk import RiskConfig, check_order_risk, risk_config_for_profile
from quant_trading.strategy import moving_average_signal
from quant_trading.trading import PaperBroker, build_target_order, round_down_to_lot


def main() -> None:
    parser = ArgumentParser(description="生成新手友好的静态 HTML 量化交易报告。")
    parser.add_argument("--symbol", default="000001", help="股票代码，如 000001、600519、sz000001")
    parser.add_argument("--start", default="20240101", help="开始日期，YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--end", default="20251231", help="结束日期，YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--source", default="auto", choices=["auto", "akshare-eastmoney", "akshare-sina", "akshare-tencent"])
    parser.add_argument("--adjust", default="qfq", choices=["", "qfq", "hfq"], help="复权方式")
    parser.add_argument("--cache", default=str(ROOT / "data" / "market_data.sqlite"), help="SQLite 缓存文件路径")
    parser.add_argument("--refresh", action="store_true", help="忽略缓存并重新请求真实数据")
    parser.add_argument("--capital-profile", default="small-2000", choices=["standard", "small-2000"], help="资金和风控预设")
    parser.add_argument("--cash", type=float, default=None, help="纸面账户现金，覆盖资金预设")
    parser.add_argument("--current-position", type=int, default=0, help="纸面账户当前持仓股数")
    parser.add_argument("--output", default=str(ROOT / "reports" / "dashboard.html"), help="HTML 输出路径")
    args = parser.parse_args()

    profile_cash, risk_config = risk_config_for_profile(args.capital_profile)
    cash = args.cash if args.cash is not None else profile_cash
    data = get_or_fetch_a_share_history(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        cache_path=args.cache,
        config=DataSourceConfig(source=args.source, adjust=args.adjust),
        refresh=args.refresh,
    )
    signal = moving_average_signal(data, fast_window=10, slow_window=30)
    backtest = run_backtest(data, signal, BacktestConfig(initial_cash=cash))
    latest_signal = float(signal.iloc[-1])
    latest_close = float(data["close"].iloc[-1])
    broker = PaperBroker(cash=cash)
    if args.current_position > 0:
        broker._increase_position(args.symbol, args.current_position, latest_close)

    if latest_signal > 0:
        target_value = min(risk_config.max_order_value, risk_config.max_position_value, cash - risk_config.min_cash_buffer)
        target_quantity = round_down_to_lot(int(target_value / latest_close), risk_config.lot_size)
        reason = "moving_average_signal=1"
    else:
        target_quantity = 0
        reason = "moving_average_signal=0"

    order = build_target_order(args.symbol, broker.position_quantity(args.symbol), target_quantity, latest_close, reason)
    decision = None
    if order is not None:
        decision = check_order_risk(
            order,
            broker.cash,
            broker.positions,
            {args.symbol: latest_close},
            risk_config,
        )

    context = HtmlReportContext(
        symbol=args.symbol,
        trade_date=str(data["date"].iloc[-1].date()),
        source=data.attrs.get("source", args.source),
        cache_status=data.attrs.get("cache_status", "disabled"),
        capital_profile=args.capital_profile,
        cash=cash,
        latest_close=latest_close,
        latest_signal=latest_signal,
        risk_config=risk_config,
        order=order,
        decision=decision,
        backtest=backtest,
    )
    write_html_report(args.output, context)
    print(f"HTML 报告已生成: {args.output}")


if __name__ == "__main__":
    main()
