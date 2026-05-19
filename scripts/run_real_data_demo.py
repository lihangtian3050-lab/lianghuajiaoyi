from argparse import ArgumentParser
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_trading.backtest import BacktestConfig, run_backtest
from quant_trading.data_cache import get_or_fetch_a_share_history
from quant_trading.data_sources import DataSourceConfig, fetch_a_share_history
from quant_trading.strategy import moving_average_signal


def main() -> None:
    parser = ArgumentParser(description="Fetch real A-share data and run a moving-average backtest.")
    parser.add_argument("--symbol", default="000001", help="股票代码，如 000001、600519、sz000001")
    parser.add_argument("--start", default="20240101", help="开始日期，YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--end", default="20251231", help="结束日期，YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument(
        "--source",
        default="auto",
        choices=["auto", "akshare-eastmoney", "akshare-sina", "akshare-tencent"],
        help="真实行情数据源",
    )
    parser.add_argument("--adjust", default="qfq", choices=["", "qfq", "hfq"], help="复权方式")
    parser.add_argument("--cache", default=str(ROOT / "data" / "market_data.sqlite"), help="SQLite 缓存文件路径")
    parser.add_argument("--refresh", action="store_true", help="忽略缓存并重新请求真实数据")
    args = parser.parse_args()

    config = DataSourceConfig(source=args.source, adjust=args.adjust)
    if args.cache:
        data = get_or_fetch_a_share_history(
            symbol=args.symbol,
            start_date=args.start,
            end_date=args.end,
            cache_path=args.cache,
            config=config,
            refresh=args.refresh,
        )
    else:
        data = fetch_a_share_history(symbol=args.symbol, start_date=args.start, end_date=args.end, config=config)
    signal = moving_average_signal(data, fast_window=10, slow_window=30)
    result = run_backtest(data, signal, BacktestConfig(initial_cash=100_000))

    print("真实 A 股数据回测演示")
    print(f"请求数据源: {args.source}")
    print(f"实际数据源: {data.attrs.get('source', args.source)}")
    print(f"缓存状态: {data.attrs.get('cache_status', 'disabled')}")
    print(f"股票代码: {args.symbol}")
    print(f"日期范围: {data['date'].min().date()} ~ {data['date'].max().date()}")
    print(f"交易日数量: {len(data)}")
    print(f"最终净值: {result.equity_curve['equity'].iloc[-1]:,.2f}")
    print(f"累计收益: {result.metrics.total_return:.2%}")
    print(f"最大回撤: {result.metrics.max_drawdown:.2%}")
    print(f"夏普比率: {result.metrics.sharpe_ratio:.2f}")


if __name__ == "__main__":
    main()
