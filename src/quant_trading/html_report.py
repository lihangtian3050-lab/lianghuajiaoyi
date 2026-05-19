from __future__ import annotations

from dataclasses import dataclass
from html import escape
import json
from pathlib import Path

import pandas as pd

from quant_trading.analysis import TechnicalAnalysis
from quant_trading.backtest import BacktestResult
from quant_trading.news import NewsCheck
from quant_trading.risk import RiskConfig, RiskDecision
from quant_trading.trading import Order


@dataclass(frozen=True)
class HtmlReportContext:
    symbol: str
    trade_date: str
    source: str
    cache_status: str
    capital_profile: str
    cash: float
    latest_close: float
    latest_signal: float
    risk_config: RiskConfig
    order: Order | None
    decision: RiskDecision | None
    backtest: BacktestResult
    analysis: TechnicalAnalysis
    news: NewsCheck


def write_html_report(path: str | Path, context: HtmlReportContext) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_html_report(context), encoding="utf-8")


def render_html_report(context: HtmlReportContext) -> str:
    chart_data = _chart_data(context.backtest.equity_curve)
    metrics = context.backtest.metrics
    order_text = "无需调仓"
    risk_text = "无订单"
    risk_reasons = ""
    if context.order is not None:
        order_text = f"{context.order.side} {context.order.quantity} 股 @ {context.order.price:.2f}"
        if context.decision is not None:
            risk_text = "通过" if context.decision.approved else "拒绝"
            risk_reasons = "<br>".join(escape(reason) for reason in context.decision.reasons)

    payload = json.dumps(chart_data, ensure_ascii=False)
    title = f"{context.symbol} 量化研究报告"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>
    :root {{
      --ink:#17202a; --muted:#64748b; --line:#d8dee9; --panel:#fff; --bg:#f4f7fb;
      --blue:#2563eb; --green:#16803c; --red:#b42318; --amber:#a15c07;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif; background:var(--bg); color:var(--ink); }}
    header {{ padding:28px 32px 18px; background:#fff; border-bottom:1px solid var(--line); }}
    h1 {{ margin:0 0 10px; font-size:28px; font-weight:700; letter-spacing:0; }}
    h2 {{ margin:0 0 14px; font-size:18px; letter-spacing:0; }}
    h3 {{ margin:0 0 8px; font-size:15px; letter-spacing:0; }}
    main {{ max-width:1180px; margin:0 auto; padding:24px; }}
    .meta {{ color:var(--muted); font-size:14px; display:flex; gap:16px; flex-wrap:wrap; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:14px; margin-bottom:18px; }}
    .two {{ display:grid; grid-template-columns:1.1fr .9fr; gap:14px; margin-bottom:18px; }}
    .panel {{ background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px; }}
    .label {{ color:var(--muted); font-size:13px; margin-bottom:8px; }}
    .value {{ font-size:22px; font-weight:700; }}
    .wide {{ margin-bottom:18px; }}
    .chart-wrap {{ height:340px; }}
    canvas {{ width:100%; height:100%; display:block; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th, td {{ padding:10px 8px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); font-weight:600; width:140px; }}
    ul {{ margin:8px 0 0; padding-left:20px; line-height:1.7; }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .status-ok {{ color:var(--green); font-weight:700; }}
    .status-bad {{ color:var(--red); font-weight:700; }}
    .status-warn {{ color:var(--amber); font-weight:700; }}
    .muted {{ color:var(--muted); }}
    .notice {{ color:var(--muted); line-height:1.7; }}
    @media (max-width:860px) {{ header{{padding:22px 18px 14px}} main{{padding:14px}} .grid{{grid-template-columns:repeat(2,minmax(0,1fr))}} .two{{grid-template-columns:1fr}} }}
    @media (max-width:520px) {{ .grid{{grid-template-columns:1fr}} .chart-wrap{{height:280px}} }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <div class="meta">
      <span>交易日期：{escape(context.trade_date)}</span>
      <span>数据源：{escape(context.source)}</span>
      <span>缓存：{escape(context.cache_status)}</span>
      <span>资金预设：{escape(context.capital_profile)}</span>
    </div>
  </header>
  <main>
    <section class="grid">
      {_card("最新收盘价", f"{context.latest_close:.2f}")}
      {_card("策略信号", "持有/买入观察" if context.latest_signal > 0 else "空仓/卖出观察")}
      {_card("累计收益", f"{metrics.total_return:.2%}")}
      {_card("最大回撤", f"{metrics.max_drawdown:.2%}")}
    </section>

    <section class="panel wide">
      <h2>清晰分析结论</h2>
      <p class="notice">{escape(context.analysis.research_conclusion)}</p>
      <p class="notice">这不是自动买卖指令，也不构成投资建议；它是基于当前规则、行情数据和风控约束生成的研究结论，最终决策需要人工确认。</p>
    </section>

    <section class="two">
      <div class="panel">
        <h2>行情分析</h2>
        <table>
          <tr><th>趋势状态</th><td>{escape(context.analysis.trend_label)}</td></tr>
          <tr><th>信号解释</th><td>{escape(context.analysis.signal_label)}</td></tr>
          <tr><th>10 日均线</th><td>{context.analysis.ma_fast:.2f}</td></tr>
          <tr><th>30 日均线</th><td>{context.analysis.ma_slow:.2f}</td></tr>
          <tr><th>20 日涨跌幅</th><td>{context.analysis.return_20d:.2%}</td></tr>
          <tr><th>60 日涨跌幅</th><td>{context.analysis.return_60d:.2%}</td></tr>
          <tr><th>20 日年化波动</th><td>{context.analysis.volatility_20d:.2%}</td></tr>
          <tr><th>60 日价格区间</th><td>{context.analysis.low_60d:.2f} - {context.analysis.high_60d:.2f}</td></tr>
        </table>
      </div>
      <div class="panel">
        <h2>风险提示</h2>
        <ul>{''.join(f'<li>{escape(note)}</li>' for note in context.analysis.risk_notes)}</ul>
      </div>
    </section>

    <section class="panel wide">
      <h2>净值与回撤</h2>
      <div class="chart-wrap"><canvas id="equityChart"></canvas></div>
    </section>

    <section class="grid">
      {_card("年化收益", f"{metrics.annual_return:.2%}")}
      {_card("年化波动", f"{metrics.annual_volatility:.2%}")}
      {_card("夏普比率", f"{metrics.sharpe_ratio:.2f}")}
      {_card("纸面现金", f"{context.cash:,.2f}")}
    </section>

    <section class="panel wide">
      <h2>新闻核验</h2>
      {_render_news(context.news)}
    </section>

    <section class="panel wide">
      <h2>候选订单与风控</h2>
      <table>
        <tr><th>计划订单</th><td>{escape(order_text)}</td></tr>
        <tr><th>风控结果</th><td class="{_risk_class(context.decision)}">{escape(risk_text)}</td></tr>
        <tr><th>拒绝原因</th><td>{risk_reasons or '<span class="muted">无</span>'}</td></tr>
        <tr><th>风控参数</th><td>单笔 {context.risk_config.max_order_value:.2f}，单票 {context.risk_config.max_position_value:.2f}，持仓比例 {context.risk_config.max_position_pct:.0%}，现金缓冲 {context.risk_config.min_cash_buffer:.2f}</td></tr>
      </table>
    </section>
  </main>
  <script>
    const chartData = {payload};
    const canvas = document.getElementById("equityChart");
    const ctx = canvas.getContext("2d");
    function resizeCanvas() {{
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      canvas.width = Math.max(300, Math.floor(rect.width * ratio));
      canvas.height = Math.max(220, Math.floor(rect.height * ratio));
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      draw();
    }}
    function scale(values, minY, maxY, height, pad) {{
      return values.map(v => pad + (maxY - v) / Math.max(maxY - minY, 1e-9) * (height - pad * 2));
    }}
    function drawLine(points, color, width) {{
      if (!points.length) return;
      ctx.beginPath();
      ctx.moveTo(points[0].x, points[0].y);
      points.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.stroke();
    }}
    function draw() {{
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);
      const pad = 34;
      ctx.strokeStyle = "#d8dee9";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(pad, pad);
      ctx.lineTo(pad, h - pad);
      ctx.lineTo(w - pad, h - pad);
      ctx.stroke();
      const equity = chartData.map(d => d.equity);
      const drawdown = chartData.map(d => d.drawdown);
      const minEq = Math.min(...equity);
      const maxEq = Math.max(...equity);
      const xs = chartData.map((_, i) => pad + i / Math.max(chartData.length - 1, 1) * (w - pad * 2));
      const eqY = scale(equity, minEq, maxEq, h, pad);
      const ddY = scale(drawdown, Math.min(...drawdown), 0, h, pad);
      drawLine(xs.map((x, i) => ({{ x, y: eqY[i] }})), "#2563eb", 2);
      drawLine(xs.map((x, i) => ({{ x, y: ddY[i] }})), "#b42318", 1.5);
      ctx.fillStyle = "#64748b";
      ctx.font = "12px Microsoft YaHei, Segoe UI, Arial";
      ctx.fillText("蓝线：净值", pad + 8, pad + 16);
      ctx.fillText("红线：回撤", pad + 8, pad + 34);
    }}
    window.addEventListener("resize", resizeCanvas);
    resizeCanvas();
  </script>
</body>
</html>
"""


def _card(label: str, value: str) -> str:
    return f'<div class="panel"><div class="label">{escape(label)}</div><div class="value">{escape(value)}</div></div>'


def _risk_class(decision: RiskDecision | None) -> str:
    if decision is None:
        return ""
    return "status-ok" if decision.approved else "status-bad"


def _render_news(news: NewsCheck) -> str:
    status_class = "status-ok" if news.status == "ok" else "status-warn"
    blocks = [f'<p class="{status_class}">{escape(news.message)}</p>']
    if news.items:
        blocks.append("<table><tr><th>时间</th><th>来源</th><th>标题</th></tr>")
        for item in news.items:
            title = escape(item.title)
            url = escape(item.url)
            linked_title = f'<a href="{url}" target="_blank" rel="noreferrer">{title}</a>' if item.url else title
            blocks.append(f"<tr><td>{escape(item.publish_time)}</td><td>{escape(item.source)}</td><td>{linked_title}</td></tr>")
        blocks.append("</table>")
    blocks.append("<h3>人工核验入口</h3><ul>")
    for label, url in news.verification_links:
        blocks.append(f'<li><a href="{escape(url)}" target="_blank" rel="noreferrer">{escape(label)}</a></li>')
    blocks.append("</ul>")
    return "".join(blocks)


def _chart_data(equity_curve: pd.DataFrame) -> list[dict[str, float | str]]:
    rows = []
    for _, row in equity_curve.iterrows():
        rows.append(
            {
                "date": str(pd.to_datetime(row["date"]).date()),
                "equity": round(float(row["equity"]), 4),
                "drawdown": round(float(row["drawdown"]), 6),
            }
        )
    return rows
