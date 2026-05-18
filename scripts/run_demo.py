from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_trading.backtest import BacktestConfig, run_backtest
from quant_trading.data import generate_sample_ohlcv, validate_ohlcv
from quant_trading.strategy import moving_average_signal


def main() -> None:
    data = generate_sample_ohlcv(symbol="SAMPLE", periods=260, seed=42)
    validate_ohlcv(data)

    signal = moving_average_signal(data, fast_window=10, slow_window=30)
    result = run_backtest(data, signal, BacktestConfig(initial_cash=100_000))

    metrics = result.metrics
    print("股票量化交易 MVP 演示")
    print(f"交易日数量: {len(data)}")
    print(f"最终净值: {result.equity_curve['equity'].iloc[-1]:,.2f}")
    print(f"累计收益: {metrics.total_return:.2%}")
    print(f"年化收益: {metrics.annual_return:.2%}")
    print(f"最大回撤: {metrics.max_drawdown:.2%}")
    print(f"夏普比率: {metrics.sharpe_ratio:.2f}")


if __name__ == "__main__":
    main()
