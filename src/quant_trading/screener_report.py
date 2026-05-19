from __future__ import annotations

from html import escape

from quant_trading.screener import ScreenResult, StockAnalysis


STYLE = """
  <style>
    :root { --ink:#17202a; --muted:#64748b; --line:#d8dee9; --bg:#f4f7fb; --panel:#fff; --blue:#2563eb; --red:#b42318; --green:#16803c; --soft:#eef4ff; --warn:#fff7ed; }
    * { box-sizing:border-box; }
    body { margin:0; font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif; background:var(--bg); color:var(--ink); }
    header { background:#ffffff; border-bottom:1px solid var(--line); padding:24px 32px; }
    main { max-width:1240px; margin:0 auto; padding:20px; }
    h1 { margin:0 0 8px; font-size:28px; letter-spacing:0; }
    h2 { margin:0 0 12px; font-size:18px; letter-spacing:0; }
    h3 { margin:0 0 8px; font-size:16px; letter-spacing:0; }
    .meta, .muted { color:var(--muted); line-height:1.7; }
    .panel { background:#fff; border:1px solid var(--line); border-radius:8px; padding:16px; margin-bottom:16px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
    .grid { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:12px; }
    .metric { border:1px solid var(--line); border-radius:8px; padding:12px; background:#fff; }
    .metric span { display:block; color:var(--muted); font-size:13px; margin-bottom:5px; }
    .metric strong { font-size:20px; }
    table { width:100%; border-collapse:collapse; font-size:14px; }
    th, td { border-bottom:1px solid var(--line); padding:10px 8px; vertical-align:top; text-align:left; }
    th { color:var(--muted); font-weight:600; white-space:nowrap; }
    ul { margin:0; padding-left:18px; line-height:1.7; }
    a { color:var(--blue); text-decoration:none; }
    a:hover { text-decoration:underline; }
    .pos { color:var(--red); font-weight:700; }
    .neg { color:var(--green); font-weight:700; }
    .topnav { display:flex; gap:12px; flex-wrap:wrap; margin-top:10px; }
    .topnav a, .button { border:1px solid var(--line); border-radius:6px; padding:7px 10px; background:#fff; display:inline-flex; align-items:center; min-height:36px; }
    .pill { display:inline-block; border:1px solid var(--line); border-radius:999px; padding:4px 9px; background:var(--soft); color:#1d4ed8; font-size:13px; }
    .warn { background:var(--warn); border-color:#fed7aa; }
    .cards { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
    .card { border:1px solid var(--line); border-radius:8px; padding:14px; background:#fff; }
    @media (max-width: 860px) { header { padding:20px 16px; } main { padding:14px; } .grid, .cards { grid-template-columns:1fr; } table { font-size:13px; } th, td { padding:8px 6px; } }
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
    steps = "".join(
        f"<li><strong>{escape(step.stage)}</strong>：{escape(step.status)}，{escape(step.message)}</li>"
        for step in result.research_steps
    )
    cards = "".join(_candidate_card(candidate) for candidate in result.candidates)
    strategy_label = _strategy_label(result.strategy)
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
    <h1>实时盯盘选股</h1>
    <div class="meta">策略：<span class="pill">{escape(strategy_label)}</span> | 状态：{escape(result.message)} | 页面每 {refresh_seconds} 秒自动刷新</div>
    <div class="topnav"><a href="/">返回控制台</a><a href="/watch?strategy=momentum">动量策略</a><a href="/watch?strategy=breakout">突破策略</a><a href="/watch?strategy=reversal">反转观察</a><a href="/watch?strategy=overnight_yang">一夜持股观察</a></div>
  </header>
  <main>
    <section class="panel">
      <h2>研究流程</h2>
      <ul>{steps}</ul>
    </section>
    <section class="panel">
      <h2>热门板块</h2>
      <ul>{boards or '<li class="muted">板块数据暂不可用。</li>'}</ul>
    </section>
    <section class="panel">
      <h2>策略候选股</h2>
      <p class="muted">以下是规则筛出的研究候选，不是买入建议。请结合报告、新闻原文、财务数据和个人风险承受能力人工确认。</p>
      <table>
        <tr><th>代码</th><th>名称</th><th>价格</th><th>涨跌幅</th><th>策略分</th><th>理由</th><th>情绪</th><th>新闻佐证</th><th>核验</th></tr>
        {rows}
      </table>
    </section>
    <section class="panel">
      <h2>候选研究卡片</h2>
      <div class="cards">{cards or '<p class="muted">暂无可展开候选。</p>'}</div>
    </section>
  </main>
</body>
</html>"""


def render_stock_analysis_html(analysis: StockAnalysis) -> str:
    steps = "".join(
        f"<li><strong>{escape(step.stage)}</strong>：{escape(step.status)}，{escape(step.message)}</li>"
        for step in analysis.research_steps
    )
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
    <h1>{escape(analysis.name)} <span class="pill">{escape(analysis.symbol)}</span></h1>
    <div class="meta">状态：{escape(analysis.message)} | 情绪：{escape(analysis.sentiment_label)}</div>
    <div class="topnav"><a href="/">返回控制台</a><a href="/watch?strategy=breakout">返回盯盘</a></div>
  </header>
  <main>
    <section class="panel">
      <h2>行情快照</h2>
      <div class="grid">
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
    <section class="panel warn">
      <h2>人工确认清单</h2>
      <ul>{checklist}</ul>
    </section>
    <section class="panel">
      <h2>研究流程</h2>
      <ul>{steps}</ul>
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
    return f"""<article class="card">
      <h3><a href="/stock?symbol={escape(candidate.code)}">{escape(candidate.name)} {escape(candidate.code)}</a></h3>
      <p class="muted">策略：{escape(_strategy_label(candidate.strategy))} | 分数：{candidate.score:.2f} | 情绪：{escape(candidate.sentiment_label)}</p>
      <ul>{reasons}</ul>
    </article>"""


def _strategy_match_card(candidate) -> str:
    reasons = "".join(f"<li>{escape(reason)}</li>" for reason in candidate.reasons)
    return f"""<article class="card">
      <h3>{escape(_strategy_label(candidate.strategy))} <span class="pill">{candidate.score:.2f}</span></h3>
      <ul>{reasons}</ul>
    </article>"""


def _news_item(item) -> str:
    title = escape(item.title)
    if item.url:
        title = f'<a href="{escape(item.url)}" target="_blank" rel="noreferrer">{title}</a>'
    meta = " ".join(part for part in [item.publish_time, item.source] if part)
    return f"<li>{title}<br><span class=\"muted\">{escape(meta)}</span></li>"


def _price_text(price: float) -> str:
    return f"{price:.2f}" if price > 0 else "待实时确认"


def _strategy_label(strategy: str) -> str:
    return {
        "momentum": "动量策略",
        "breakout": "突破策略",
        "reversal": "反转观察",
        "overnight_yang": "杨永兴风格隔夜观察",
    }.get(strategy, strategy)
