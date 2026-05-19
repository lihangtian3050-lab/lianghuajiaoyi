from argparse import ArgumentParser
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_trading.report_workflow import generate_html_report


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

    generate_html_report(
        output_path=args.output,
        symbol=args.symbol,
        start_date=args.start,
        end_date=args.end,
        source=args.source,
        adjust=args.adjust,
        cache_path=args.cache,
        capital_profile=args.capital_profile,
        cash=args.cash,
        current_position=args.current_position,
        refresh=args.refresh,
    )
    print(f"HTML 报告已生成: {args.output}")


if __name__ == "__main__":
    main()
