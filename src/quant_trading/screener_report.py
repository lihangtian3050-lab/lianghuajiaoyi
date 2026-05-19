from __future__ import annotations

from html import escape

from quant_trading.screener import ScreenResult


def render_screener_html(result: ScreenResult, refresh_seconds: int = 60) -> str:
    refresh = f'<meta http-equiv="refresh" content="{refresh_seconds}">' if refresh_seconds > 0 else ""
    rows = "".join(_candidate_row(candidate) for candidate in result.candidates)
    if not rows:
        rows = '<tr><td colspan="9" class="muted">暂无候选。请稍后刷新，或切换策略。</td></tr>'
    boards = "".join(
        f"<li>{escape(board.name)}：{board.pct_change:.2f}% 领涨 {escape(board.leader)} {board.leader_pct:.2f}%</li>"
        for board in result.hot_boards
    )
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  {refresh}
  <title>实时盯盘选股</title>
  <style>
    :root {{ --ink:#17202a; --muted:#64748b; --line:#d8dee9; --bg:#f4f7fb; --panel:#fff; --blue:#2563eb; --red:#b42318; --green:#16803c; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif; background:var(--bg); color:var(--ink); }}
    header {{ background:#fff; border-bottom:1px solid var(--line); padding:24px 32px; }}
    main {{ max-width:1240px; margin:0 auto; padding:20px; }}
    h1 {{ margin:0 0 8px; font-size:28px; }}
    h2 {{ margin:0 0 12px; font-size:18px; }}
    .meta, .muted {{ color:var(--muted); }}
    .panel {{ background:#fff; border:1px solid var(--line); border-radius:8px; padding:16px; margin-bottom:16px; }}
    table {{ width:100%; border-collapse:collapse; font-size:14px; }}
    th, td {{ border-bottom:1px solid var(--line); padding:10px 8px; vertical-align:top; text-align:left; }}
    th {{ color:var(--muted); font-weight:600; white-space:nowrap; }}
    ul {{ margin:0; padding-left:18px; line-height:1.7; }}
    a {{ color:var(--blue); text-decoration:none; }}
    a:hover {{ text-decoration:underline; }}
    .pos {{ color:var(--red); font-weight:700; }}
    .neg {{ color:var(--green); font-weight:700; }}
    .topnav {{ display:flex; gap:12px; flex-wrap:wrap; margin-top:10px; }}
    .topnav a {{ border:1px solid var(--line); border-radius:6px; padding:7px 10px; background:#fff; }}
  </style>
</head>
<body>
  <header>
    <h1>实时盯盘选股</h1>
    <div class="meta">策略：{escape(result.strategy)} ｜ 状态：{escape(result.message)} ｜ 页面每 {refresh_seconds} 秒自动刷新</div>
    <div class="topnav"><a href="/">返回控制台</a><a href="/watch?strategy=momentum">动量策略</a><a href="/watch?strategy=breakout">突破策略</a><a href="/watch?strategy=reversal">反转观察</a></div>
  </header>
  <main>
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
      <td>{escape(candidate.code)}</td>
      <td>{escape(candidate.name)}</td>
      <td>{candidate.price:.2f}</td>
      <td class="{pct_class}">{candidate.pct_change:.2f}%</td>
      <td>{candidate.score:.2f}</td>
      <td><ul>{reasons}</ul></td>
      <td>{escape(candidate.sentiment_label)}</td>
      <td><ul>{news_titles}</ul></td>
      <td><ul>{links}</ul></td>
    </tr>"""
