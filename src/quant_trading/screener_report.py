from __future__ import annotations

from datetime import datetime
from html import escape

from quant_trading.screener import ScreenResult, StockAnalysis


STYLE = """
  <style>
    :root {
      --ink:#18212f; --muted:#667085; --soft:#eef2f7; --line:#d7dde7;
      --panel:#ffffff; --wash:#f6f8fb; --nav:#172033; --nav-2:#202b42;
      --blue:#1f5eff; --blue-soft:#edf4ff; --red:#b42318; --green:#087443;
      --amber:#b45309; --amber-soft:#fff7ed; --cyan:#0e7490;
      --shadow:0 14px 34px rgba(24,33,47,.08);
    }
    * { box-sizing:border-box; }
    body {
      margin:0; color:var(--ink); font-family:"Microsoft YaHei","Segoe UI",sans-serif;
      background:var(--wash);
    }
    header { background:var(--nav); color:#fff; border-bottom:1px solid rgba(255,255,255,.08); }
    main { width:min(1440px, calc(100vw - 40px)); margin:0 auto; padding:18px 0 28px; }
    h1 { margin:0; font-size:26px; letter-spacing:0; }
    h2 { margin:0 0 12px; font-size:17px; letter-spacing:0; }
    h3 { margin:0 0 8px; font-size:14px; letter-spacing:0; }
    p { margin:0; }
    ul { margin:0; padding-left:18px; line-height:1.55; }
    a { color:var(--blue); text-decoration:none; }
    a:hover { text-decoration:underline; }
    .muted, .meta { color:var(--muted); line-height:1.6; }
    header .meta { color:#b8c2d8; }
    .topline { width:min(1440px, calc(100vw - 40px)); margin:0 auto; padding:20px 0 14px; display:flex; align-items:flex-start; justify-content:space-between; gap:16px; flex-wrap:wrap; }
    .topnav { width:min(1440px, calc(100vw - 40px)); margin:0 auto; display:flex; gap:8px; flex-wrap:wrap; padding:0 0 16px; }
    .topnav a, .button {
      border:1px solid rgba(255,255,255,.16); border-radius:7px; padding:8px 11px; background:var(--nav-2);
      display:inline-flex; align-items:center; min-height:36px; color:#dce7ff; text-decoration:none;
      font-weight:600;
    }
    .topnav a:hover { background:#263756; text-decoration:none; }
    .pill {
      display:inline-flex; align-items:center; border:1px solid var(--line); border-radius:999px;
      padding:4px 9px; background:var(--blue-soft); color:#1d4ed8; font-size:13px; white-space:nowrap;
    }
    header .pill { border-color:rgba(255,255,255,.18); background:#eaf1ff; }
    .pill.warn { background:var(--amber-soft); color:var(--amber); border-color:#fed7aa; }
    .toolbar {
      display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:10px; margin-bottom:14px;
    }
    .banner {
      border:1px solid #fed7aa; background:var(--amber-soft); color:#7c2d12;
      border-radius:8px; padding:12px 14px; margin-bottom:14px; line-height:1.65;
    }
    .workbench { display:grid; grid-template-columns:minmax(0,1fr) 360px; gap:16px; align-items:start; }
    .side { position:sticky; top:14px; display:grid; gap:12px; }
    .panel {
      background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:16px;
      box-shadow:0 1px 2px rgba(15,23,42,.04);
    }
    .metric-list { display:grid; gap:10px; grid-template-columns:1fr; }
    .metric {
      border:1px solid var(--line); border-radius:8px; padding:12px; background:#fff;
      box-shadow:0 1px 2px rgba(15,23,42,.04);
    }
    .metric span { display:block; color:var(--muted); font-size:12px; margin-bottom:6px; }
    .metric strong { display:block; font-size:19px; line-height:1.25; overflow-wrap:anywhere; font-variant-numeric:tabular-nums; }
    .candidate-section { display:grid; gap:14px; }
    .cards { display:grid; gap:12px; }
    .card {
      border:1px solid var(--line); border-radius:8px; padding:14px; background:#fff;
      box-shadow:var(--shadow); position:relative; overflow:hidden;
    }
    .card::before { content:""; position:absolute; inset:0 auto 0 0; width:4px; background:var(--blue); }
    .card-head { display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:10px; }
    .card-title a { font-weight:700; color:var(--ink); text-decoration:none; }
    .card-title a:hover { color:var(--blue); }
    .card-sub { color:var(--muted); font-size:13px; margin-top:4px; }
    .score { font-size:22px; font-weight:800; color:var(--blue); text-align:right; font-variant-numeric:tabular-nums; }
    .facts { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:8px; margin:10px 0; }
    .fact { border:1px solid var(--line); border-radius:8px; padding:8px; background:#fbfdff; min-width:0; }
    .fact span { display:block; color:var(--muted); font-size:12px; margin-bottom:3px; }
    .fact strong { display:block; font-size:14px; overflow-wrap:anywhere; }
    .card-body { display:grid; grid-template-columns:1.1fr .9fr; gap:14px; }
    .card-actions { display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }
    .card-actions a { border:1px solid var(--line); border-radius:7px; padding:7px 10px; background:#f8fbff; font-weight:600; }
    .steps { display:grid; gap:10px; }
    .step { border:1px solid var(--line); border-radius:8px; padding:10px; background:#fff; }
    .step strong { display:block; margin-bottom:6px; }
    .status { display:inline-flex; align-items:center; border-radius:999px; padding:2px 7px; font-size:12px; margin-bottom:6px; background:#ecfdf3; color:#027a48; }
    .status.warn, .status.error, .status.fallback { background:var(--amber-soft); color:var(--amber); }
    .boards { display:flex; flex-wrap:wrap; gap:8px; padding:0; margin:0; list-style:none; }
    .boards li { border:1px solid var(--line); border-radius:999px; padding:7px 10px; color:var(--muted); background:#fff; }
    .detail { overflow-x:auto; }
    table { width:100%; min-width:1040px; border-collapse:collapse; font-size:14px; }
    th, td { border-bottom:1px solid var(--line); padding:10px 8px; vertical-align:top; text-align:left; }
    th { color:var(--muted); font-weight:600; white-space:nowrap; }
    details summary { cursor:pointer; color:var(--blue); font-weight:700; }
    .pos { color:var(--red); font-weight:700; }
    .neg { color:var(--green); font-weight:700; }
    .stock-layout { display:grid; gap:14px; }
    .stock-summary { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
    .risk-note { border-left:4px solid var(--amber); background:#fffaf0; padding:10px 12px; border-radius:8px; color:#7c2d12; }
    @media (max-width: 1180px) {
      main { width:min(100%, calc(100vw - 28px)); }
      .workbench { grid-template-columns:1fr; }
      .side { position:static; }
      .metric-list, .steps { grid-template-columns:repeat(2,minmax(0,1fr)); }
    }
    @media (max-width: 860px) {
      header { padding:18px 16px; }
      header .topline, header .topnav, main { width:min(100%, calc(100vw - 24px)); }
      .toolbar, .card-body, .facts, .metric-list, .steps, .stock-summary { grid-template-columns:1fr; }
    }
  </style>
"""


def render_screener_html(result: ScreenResult, refresh_seconds: int = 60) -> str:
    refresh = f'<meta http-equiv="refresh" content="{refresh_seconds}">' if refresh_seconds > 0 else ""
    rows = "".join(_candidate_row(candidate) for candidate in result.candidates)
    if not rows:
        rows = '<tr><td colspan="9" class="muted">暂无候选。请稍后刷新，或切换策略。</td></tr>'
    boards = "".join(
        f"<li>{escape(board.name)}：{board.pct_change:.2f}% 领涨 {escape(board.leader)} {board.leader_pct:.2f}%</li>"
        for board in result.hot_boards
    )
    steps = "".join(_step_card(step) for step in result.research_steps)
    cards = "".join(_candidate_card(candidate) for candidate in result.candidates)
    strategy_label = _strategy_label(result.strategy)
    source_label = _quote_source_label(result)
    updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {refresh}
  <title>实时盯盘选股</title>
  {STYLE}
</head>
<body>
  <header>
    <div class="topline">
      <div>
        <h1>实时盯盘选股</h1>
        <div class="meta">策略：{escape(strategy_label)} | 更新时间：{escape(updated_at)} | 刷新：{refresh_seconds} 秒</div>
      </div>
      <span class="pill {'warn' if result.status != 'ok' else ''}">{escape(_status_label(result.status))}</span>
    </div>
    <div class="topnav"><a href="/">返回控制台</a><a href="/watch?strategy=momentum">动量策略</a><a href="/watch?strategy=breakout">突破策略</a><a href="/watch?strategy=reversal">反转观察</a><a href="/watch?strategy=overnight_yang">一夜持股观察</a></div>
  </header>
  <main>
    {_fallback_banner(result)}
    <section class="toolbar">
      <div class="metric"><span>数据状态</span><strong>{escape(_status_label(result.status))}</strong></div>
      <div class="metric"><span>数据源</span><strong>{escape(source_label)}</strong></div>
      <div class="metric"><span>候选数量</span><strong>{len(result.candidates)}</strong></div>
      <div class="metric"><span>热门板块</span><strong>{len(result.hot_boards)}</strong></div>
      <div class="metric"><span>策略</span><strong>{escape(strategy_label)}</strong></div>
    </section>
    <section class="workbench">
      <section class="candidate-section">
        <section class="panel">
          <h2>候选研究卡片</h2>
          <div class="cards">{cards or '<p class="muted">暂无可展开候选。</p>'}</div>
        </section>
        <section class="panel">
          <details>
            <summary>展开候选明细表</summary>
            <p class="muted">以下是规则筛出的研究候选，不是买入建议。请结合报告、新闻原文、财务数据和个人风险承受能力人工确认。</p>
            <div class="detail">
              <table>
                <tr><th>代码</th><th>名称</th><th>价格</th><th>涨跌幅</th><th>策略分</th><th>理由</th><th>情绪</th><th>新闻佐证</th><th>核验</th></tr>
                {rows}
              </table>
            </div>
          </details>
        </section>
      </section>
      <aside class="side">
        <section class="panel">
          <h2>研究流程</h2>
          <div class="steps">{steps}</div>
        </section>
        <section class="panel">
          <h2>热门板块</h2>
          <ul class="boards">{boards or '<li>板块数据暂不可用。</li>'}</ul>
        </section>
        <section class="panel">
          <h2>风控提醒</h2>
          <p class="risk-note">候选只代表研究排序，不代表买点。严格信号为空时显示的是观察池，必须人工确认分时、新闻原文、财务风险和仓位。</p>
        </section>
      </aside>
    </section>
  </main>
</body>
</html>"""


def render_stock_analysis_html(analysis: StockAnalysis) -> str:
    steps = "".join(_step_card(step) for step in analysis.research_steps)
    matches = "".join(_strategy_match_card(candidate) for candidate in analysis.strategy_matches)
    news = "".join(_news_item(item) for item in analysis.news.items[:5])
    links = "".join(f'<li><a href="{escape(url)}" target="_blank" rel="noreferrer">{escape(label)}</a></li>' for label, url in analysis.news.verification_links)
    checklist = "".join(f"<li>{escape(item)}</li>" for item in analysis.checklist)
    pct_class = "pos" if analysis.pct_change >= 0 else "neg"
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(analysis.symbol)} 单票分析</title>
  {STYLE}
</head>
<body>
  <header>
    <div class="topline">
      <div>
        <h1>{escape(analysis.name)} <span class="pill">{escape(analysis.symbol)}</span></h1>
        <div class="meta">状态：{escape(analysis.message)} | 情绪：{escape(analysis.sentiment_label)}</div>
      </div>
      <span class="pill {'warn' if analysis.status != 'ok' else ''}">{escape(_status_label(analysis.status))}</span>
    </div>
    <div class="topnav"><a href="/">返回控制台</a><a href="/watch?strategy=breakout">返回盯盘</a></div>
  </header>
  <main class="stock-layout">
    <section class="panel">
      <h2>行情快照</h2>
      <div class="stock-summary">
        <div class="metric"><span>价格</span><strong>{escape(_price_text(analysis.price))}</strong></div>
        <div class="metric"><span>涨跌幅</span><strong class="{pct_class}">{analysis.pct_change:.2f}%</strong></div>
        <div class="metric"><span>成交额</span><strong>{analysis.amount/100_000_000:.2f} 亿</strong></div>
        <div class="metric"><span>量比 / 换手</span><strong>{analysis.volume_ratio:.2f} / {analysis.turnover_rate:.2f}%</strong></div>
      </div>
    </section>
    <section class="panel">
      <h2>策略匹配</h2>
      <div class="cards">{matches or '<p class="muted">当前快照未命中已启用策略，只能作为观察对象。</p>'}</div>
    </section>
    <section class="panel">
      <h2>新闻佐证与情绪</h2>
      <p class="muted">{escape(analysis.news.message)}</p>
      <ul>{news or '<li class="muted">暂无新闻条目，请使用核验链接。</li>'}</ul>
      <h3>人工核验链接</h3>
      <ul>{links}</ul>
    </section>
    <section class="panel">
      <h2>人工确认清单</h2>
      <ul>{checklist}</ul>
    </section>
    <section class="panel">
      <h2>研究流程</h2>
      <div class="steps">{steps}</div>
    </section>
  </main>
</body>
</html>"""


def _candidate_row(candidate) -> str:
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in candidate.reasons)
    news_titles = "".join(f"<li>{escape(item.title)}</li>" for item in candidate.news.items[:3])
    if not news_titles:
        news_titles = f"<li>{escape(candidate.news.message)}</li>"
    links = "".join(f'<li><a href="{escape(url)}" target="_blank" rel="noreferrer">{escape(label)}</a></li>' for label, url in candidate.news.verification_links)
    pct_class = "pos" if candidate.pct_change >= 0 else "neg"
    return f"""<tr>
      <td><a href="/stock?symbol={escape(candidate.code)}">{escape(candidate.code)}</a></td>
      <td>{escape(candidate.name)}</td>
      <td>{escape(_price_text(candidate.price))}</td>
      <td class="{pct_class}">{candidate.pct_change:.2f}%</td>
      <td>{candidate.score:.2f}</td>
      <td><ul>{reasons}</ul></td>
      <td>{escape(candidate.sentiment_label)}</td>
      <td><ul>{news_titles}</ul></td>
      <td><ul>{links}</ul></td>
    </tr>"""


def _candidate_card(candidate) -> str:
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in candidate.reasons[:4])
    action_links = "".join(f'<a href="{escape(url)}" target="_blank" rel="noreferrer">{escape(label)}</a>' for label, url in candidate.news.verification_links[:2])
    news_items = "".join(_news_item(item) for item in candidate.news.items[:2])
    if not news_items:
        news_items = f'<li class="muted">{escape(candidate.news.message)}</li>'
    pct_class = "pos" if candidate.pct_change >= 0 else "neg"
    return f"""<article class="card">
      <div class="card-head">
        <div class="card-title">
          <a href="/stock?symbol={escape(candidate.code)}">{escape(candidate.name)} {escape(candidate.code)}</a>
          <div class="card-sub">{escape(_strategy_label(candidate.strategy))} | {escape(candidate.sentiment_label)}</div>
        </div>
        <div class="score">{candidate.score:.2f}</div>
      </div>
      <div class="facts">
        <div class="fact"><span>价格</span><strong>{escape(_price_text(candidate.price))}</strong></div>
        <div class="fact"><span>涨跌幅</span><strong class="{pct_class}">{candidate.pct_change:.2f}%</strong></div>
        <div class="fact"><span>量比</span><strong>{candidate.volume_ratio:.2f}</strong></div>
        <div class="fact"><span>换手率</span><strong>{candidate.turnover_rate:.2f}%</strong></div>
      </div>
      <div class="card-body">
        <div>
          <h3>推荐理由</h3>
          <ul>{reasons}</ul>
        </div>
        <div>
          <h3>新闻情绪</h3>
          <p class="muted">情绪：{escape(candidate.sentiment_label)}</p>
          <ul>{news_items}</ul>
        </div>
      </div>
      <div class="card-actions">
        <a href="/stock?symbol={escape(candidate.code)}">单票分析</a>
        {action_links or '<span class="muted">暂无核验链接</span>'}
      </div>
    </article>"""


def _strategy_match_card(candidate) -> str:
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in candidate.reasons)
    return f"""<article class="card">
      <h3>{escape(_strategy_label(candidate.strategy))} <span class="pill">{candidate.score:.2f}</span></h3>
      <ul>{reasons}</ul>
    </article>"""


def _step_card(step) -> str:
    return f"""<article class="step">
      <span class="status {escape(step.status)}">{escape(_status_label(step.status))}</span>
      <strong>{escape(step.stage)}</strong>
      <p class="muted">{escape(step.message)}</p>
    </article>"""


def _news_item(item) -> str:
    title = escape(item.title)
    if item.url:
        title = f'<a href="{escape(item.url)}" target="_blank" rel="noreferrer">{title}</a>'
    meta = " ".join(part for part in [item.publish_time, item.source] if part)
    return f"<li>{title}<br><span class=\"muted\">{escape(meta)}</span></li>"


def _fallback_banner(result: ScreenResult) -> str:
    if result.status == "ok":
        return ""
    return f"""<div class="banner">
      当前不是完整实时数据：{escape(result.message)} 这些候选只用于研究演示和人工核验，不能直接作为买入依据。
    </div>"""


def _quote_source_label(result: ScreenResult) -> str:
    for step in result.research_steps:
        marker = "通过 "
        if step.stage == "实时行情" and marker in step.message:
            return step.message.split(marker, 1)[1].split(" 获取到", 1)[0]
    if result.status == "fallback":
        return "降级候选池"
    return "待确认"


def _price_text(price: float) -> str:
    return f"{price:.2f}" if price > 0 else "待实时确认"


def _status_label(status: str) -> str:
    return {
        "ok": "正常",
        "warn": "需核验",
        "error": "失败",
        "empty": "无数据",
        "fallback": "降级数据",
    }.get(status, status)


def _strategy_label(strategy: str) -> str:
    return {
        "momentum": "动量策略",
        "breakout": "突破策略",
        "reversal": "反转观察",
        "overnight_yang": "杨永兴风格隔夜观察",
    }.get(strategy, strategy)
