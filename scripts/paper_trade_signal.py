from argparse import ArgumentParser
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_trading.audit import append_audit_record, build_audit_record, build_run_id, write_order_review
from quant_trading.data_cache import get_or_fetch_a_share_history
from quant_trading.data_sources import DataSourceConfig
from quant_trading.risk import RiskConfig, check_order_risk
from quant_trading.strategy import moving_average_signal
from quant_trading.trading import PaperBroker, build_target_order, round_down_to_lot


def main() -> None:
    parser = ArgumentParser(description="Generate a risk-checked paper-trading order from the MA strategy.")
    parser.add_argument("--symbol", default="000001", help="stock code, for example 000001, 600519, sz000001")
    parser.add_argument("--start", default="20240101", help="start date, YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--end", default="20251231", help="end date, YYYYMMDD or YYYY-MM-DD")
    parser.add_argument("--source", default="auto", choices=["auto", "akshare-eastmoney", "akshare-sina", "akshare-tencent"])
    parser.add_argument("--adjust", default="qfq", choices=["", "qfq", "hfq"], help="adjustment mode")
    parser.add_argument("--cache", default=str(ROOT / "data" / "market_data.sqlite"), help="SQLite cache path")
    parser.add_argument("--refresh", action="store_true", help="ignore cache and fetch data again")
    parser.add_argument("--cash", type=float, default=100_000.0, help="paper account cash")
    parser.add_argument("--current-position", type=int, default=0, help="current paper position shares")
    parser.add_argument("--max-order-value", type=float, default=20_000.0)
    parser.add_argument("--max-position-value", type=float, default=30_000.0)
    parser.add_argument("--max-position-pct", type=float, default=0.30)
    parser.add_argument("--min-cash-buffer", type=float, default=10_000.0)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--audit", default=str(ROOT / "reports" / "audit_trail.csv"), help="audit CSV path")
    parser.add_argument("--orders-dir", default=str(ROOT / "reports"), help="manual review order directory")
    parser.add_argument("--paper-fill", action="store_true", help="also execute the approved order in the paper broker")
    args = parser.parse_args()

    data = get_or_fetch_a_share_history(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        cache_path=args.cache,
        config=DataSourceConfig(source=args.source, adjust=args.adjust),
        refresh=args.refresh,
    )
    signal = moving_average_signal(data, fast_window=10, slow_window=30)
    latest_signal = float(signal.iloc[-1])
    latest_close = float(data["close"].iloc[-1])

    broker = PaperBroker(cash=args.cash)
    if args.current_position > 0:
        broker._increase_position(args.symbol, args.current_position, latest_close)

    risk_config = RiskConfig(
        max_order_value=args.max_order_value,
        max_position_value=args.max_position_value,
        max_position_pct=args.max_position_pct,
        min_cash_buffer=args.min_cash_buffer,
        lot_size=args.lot_size,
    )

    if latest_signal > 0:
        target_value = min(args.max_order_value, args.max_position_value, args.cash - args.min_cash_buffer)
        target_quantity = round_down_to_lot(int(target_value / latest_close), args.lot_size)
        reason = "moving_average_signal=1"
    else:
        target_quantity = 0
        reason = "moving_average_signal=0"

    current_quantity = broker.position_quantity(args.symbol)
    order = build_target_order(args.symbol, current_quantity, target_quantity, latest_close, reason)
    trade_date = str(data["date"].iloc[-1].date())
    run_id = build_run_id(args.symbol, trade_date)

    print("纸面交易信号")
    print(f"股票代码: {args.symbol}")
    print(f"数据日期: {trade_date}")
    print(f"最新收盘价: {latest_close:.2f}")
    print(f"策略信号: {latest_signal:.0f}")
    print(f"缓存状态: {data.attrs.get('cache_status', 'disabled')}")

    if order is None:
        record = build_audit_record(
            run_id,
            args.symbol,
            trade_date,
            latest_close,
            latest_signal,
            None,
            None,
            data.attrs.get("source", args.source),
            data.attrs.get("cache_status", "disabled"),
        )
        append_audit_record(args.audit, record)
        write_order_review(Path(args.orders_dir) / f"orders_{run_id}.csv", record)
        print("计划订单: 无需调仓")
        print(f"审计日志: {args.audit}")
        return

    decision = check_order_risk(
        order=order,
        cash=broker.cash,
        positions=broker.positions,
        latest_prices={args.symbol: latest_close},
        config=risk_config,
    )
    record = build_audit_record(
        run_id,
        args.symbol,
        trade_date,
        latest_close,
        latest_signal,
        order,
        decision,
        data.attrs.get("source", args.source),
        data.attrs.get("cache_status", "disabled"),
    )
    append_audit_record(args.audit, record)
    order_review_path = Path(args.orders_dir) / f"orders_{run_id}.csv"
    write_order_review(order_review_path, record)

    print(f"计划订单: {order.side} {order.quantity} 股 @ {order.price:.2f}")
    print("风控结果:", "通过" if decision.approved else "拒绝")
    print(f"审计日志: {args.audit}")
    print(f"人工确认文件: {order_review_path}")
    if decision.reasons:
        for reason_text in decision.reasons:
            print(f"- {reason_text}")
        return
    if not args.paper_fill:
        print("纸面成交: 未执行。添加 --paper-fill 才会在纸面账户中模拟成交。")
        return

    fill = broker.submit_order(order)
    print(f"纸面成交: {fill.side} {fill.quantity} 股 @ {fill.fill_price:.2f}, 手续费 {fill.fee:.2f}")
    print(f"剩余现金: {broker.cash:.2f}")
    print(f"持仓股数: {broker.position_quantity(args.symbol)}")


if __name__ == "__main__":
    main()
