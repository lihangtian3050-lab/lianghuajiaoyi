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

## 下一步

1. 增加本地数据缓存，推荐 SQLite 或 DuckDB。
2. 增加多数据源交叉校验，比如同一股票同一日期的 OHLC 差异检查。
3. 扩展手续费、滑点、涨跌停、停牌处理。
4. 做策略报告可视化。
