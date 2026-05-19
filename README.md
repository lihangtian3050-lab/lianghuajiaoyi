# 股票量化交易 MVP

这个项目先聚焦三件事：

- 数据可靠：统一行情字段校验，避免脏数据直接进入策略。
- 回测可信：信号在收盘后生成，下一根 K 线才生效，避免未来函数。
- 结果可复现：默认示例数据由固定随机种子生成，离线也能重复运行。

## 快速开始

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts\run_demo.py
python -m unittest discover -s tests
```

如果你暂时不想创建虚拟环境，也可以直接运行：

```powershell
python scripts\run_demo.py
python -m unittest discover -s tests
```

## 当前功能

- 生成可复现的示例 OHLCV 日线数据
- 通过 AkShare 接入真实 A 股日线数据，默认使用东方财富接口
- 校验行情数据结构和价格关系
- 运行双均线策略
- 计算净值、回撤、年化收益、夏普比率等基础指标
- 单元测试覆盖数据校验和回测防未来函数逻辑

## 使用真实 A 股数据

默认数据源是 `auto`，会按东方财富、新浪、腾讯的顺序尝试：

```powershell
python scripts\run_real_data_demo.py --symbol 000001 --start 20240101 --end 20251231
```

默认会把真实行情缓存到 `data/market_data.sqlite`，再次运行相同参数会优先读取本地缓存。需要强制刷新时：

```powershell
python scripts\run_real_data_demo.py --symbol 000001 --start 20240101 --end 20251231 --refresh
```

也可以切换到新浪或腾讯适配器：

```powershell
python scripts\run_real_data_demo.py --symbol 600519 --source akshare-sina
python scripts\run_real_data_demo.py --symbol 000001 --source akshare-tencent
```

说明：

- `akshare-eastmoney`：优先推荐，历史日线数据质量较好，支持沪深京 A 股。
- `akshare-sina`：可用作备用源，但高频/大量请求容易被限制。
- `akshare-tencent`：可用作备用源，适合后续做交叉校验。
- 回测默认使用前复权 `qfq`，可以通过 `--adjust hfq` 或 `--adjust ""` 修改。

## 多数据源交叉校验

比较同一只股票在多个数据源中的 OHLCV 数据：

```powershell
python scripts\check_data_sources.py --symbol 000001 --start 20240101 --end 20251231
```

默认比较新浪和腾讯，也可以手动指定：

```powershell
python scripts\check_data_sources.py --symbol 600519 --sources akshare-sina akshare-tencent
```

输出会包含每个数据源的请求状态、缓存命中情况、缺失日期数量和字段差异数量。价格差异默认容忍 `0.01`，成交量差异默认容忍 `0.1%`。

## 纸面交易信号

系统可以把策略信号转换成经过风控检查的纸面订单：

```powershell
python scripts\paper_trade_signal.py --symbol 000001 --start 20240101 --end 20251231
```

如果按 2000 元小资金账户做纸面跟踪：

```powershell
python scripts\paper_trade_signal.py --symbol 000001 --start 20240101 --end 20251231 --capital-profile small-2000
```

这个脚本不会连接券商，也不会真实下单。它会生成审计日志和人工确认订单文件：

- `reports/audit_trail.csv`
- `reports/orders_*.csv`

默认只生成计划订单，不模拟成交。需要在纸面账户里模拟成交时，显式添加：

```powershell
python scripts\paper_trade_signal.py --symbol 000001 --start 20240101 --end 20251231 --paper-fill
```

默认风控包括：

- 单笔订单金额上限
- 单票持仓金额上限
- 单票持仓占总资产比例上限
- 最低现金缓冲
- A 股 100 股整手约束

## HTML 可视化报告

生成新手友好的静态网页报告：

```powershell
python scripts\generate_html_report.py --symbol 000001 --start 20240101 --end 20251231 --capital-profile small-2000
```

默认输出到：

```text
reports/dashboard.html
```

这个 HTML 文件可以直接用浏览器打开，里面包含净值曲线、回撤、收益指标、策略信号、候选订单和风控结果。
报告也会展示行情分析、规则研究结论、风险提示和新闻核验入口。新闻接口不可用时，报告会给出东方财富/百度的人工核验链接。

## 本地控制台

启动本地网页控制台：

```powershell
python scripts\local_console.py
```

然后在浏览器打开：

```text
http://127.0.0.1:8765
```

也可以启动时自动打开浏览器：

```powershell
python scripts\local_console.py --open
```

控制台可以输入股票代码、日期、数据源、资金档位和当前持仓，点击按钮后生成 `reports/dashboard.html` 并在浏览器中展示。
控制台生成的是研究报告，不是自动买卖指令；报告里的结论用于辅助人工判断，不构成投资建议。

实时盯盘选股入口：

```text
http://127.0.0.1:8765/watch?strategy=momentum
http://127.0.0.1:8765/watch?strategy=breakout
http://127.0.0.1:8765/watch?strategy=reversal
```

盯盘页会展示热门板块、策略候选、候选理由、新闻佐证、情绪标签和人工核验链接。页面默认每 60 秒刷新一次。

## 下一步

1. 扩展涨跌停、停牌、集合竞价等 A 股交易约束。
2. 增加多股票组合视图。
