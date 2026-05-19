from argparse import ArgumentParser
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_trading.data_quality import cross_check_a_share_sources


def main() -> None:
    parser = ArgumentParser(description="Cross-check A-share OHLCV data across multiple sources.")
    parser.add_argument("--symbol", default="000001", help="股票代码，如 000001、600519、sz000001")
    parser.add_argument("--start", default="20240101", help="开始日期，YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument("--end", default="20251231", help="结束日期，YYYYMMDD 或 YYYY-MM-DD")
    parser.add_argument(
        "--sources",
        nargs="+",
        default=["akshare-sina", "akshare-tencent"],
        help="要比较的数据源，至少两个",
    )
    parser.add_argument("--adjust", default="qfq", choices=["", "qfq", "hfq"], help="复权方式")
    parser.add_argument("--cache", default=str(ROOT / "data" / "market_data.sqlite"), help="SQLite 缓存文件路径")
    parser.add_argument("--refresh", action="store_true", help="忽略缓存并重新请求真实数据")
    parser.add_argument("--price-tolerance", type=float, default=0.01, help="价格绝对差异容忍度")
    parser.add_argument("--volume-tolerance-ratio", type=float, default=0.001, help="成交量相对差异容忍度")
    parser.add_argument("--limit", type=int, default=20, help="最多展示多少条差异")
    args = parser.parse_args()

    result = cross_check_a_share_sources(
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        sources=args.sources,
        adjust=args.adjust,
        cache_path=args.cache,
        refresh=args.refresh,
        price_tolerance=args.price_tolerance,
        volume_tolerance_ratio=args.volume_tolerance_ratio,
    )

    print("A 股多数据源交叉校验")
    print(f"股票代码: {args.symbol}")
    print(f"日期范围: {args.start} ~ {args.end}")
    print("数据源状态:")
    for check in result.source_checks:
        suffix = f", 错误: {check.error}" if check.error else ""
        print(
            f"- 请求 {check.requested_source}, 实际 {check.actual_source or '-'}, "
            f"行数 {check.rows}, 缓存 {check.cache_status}{suffix}"
        )

    print(f"缺失日期数量: {len(result.missing_dates)}")
    print(f"字段差异数量: {len(result.differences)}")

    if not result.missing_dates.empty:
        print("\n缺失日期样例:")
        print(result.missing_dates.head(args.limit).to_string(index=False))

    if not result.differences.empty:
        print("\n字段差异样例:")
        print(result.differences.head(args.limit).to_string(index=False))

    print("\n校验结果:", "通过" if result.passed else "发现差异")


if __name__ == "__main__":
    main()
