from __future__ import annotations

from argparse import ArgumentParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
import html
import sys
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from quant_trading.report_workflow import generate_html_report
from quant_trading.research_log import append_research_log, steps_to_dicts
from quant_trading.screener import screen_market
from quant_trading.screener_report import render_screener_html


INDEX_HTML = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>量化交易本地控制台</title>
  <style>
    :root { --ink:#17202a; --muted:#64748b; --line:#d8dee9; --bg:#f4f7fb; --panel:#fff; --blue:#2563eb; }
    * { box-sizing: border-box; }
    body { margin:0; font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif; background:var(--bg); color:var(--ink); }
    header { background:#fff; border-bottom:1px solid var(--line); padding:26px 32px; }
    h1 { margin:0 0 8px; font-size:28px; letter-spacing:0; }
    h2 { margin:0 0 12px; font-size:18px; }
    p { margin:0; color:var(--muted); }
    main { max-width:1040px; margin:0 auto; padding:24px; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:8px; padding:18px; margin-bottom:16px; }
    form { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:14px; }
    label { display:block; font-size:13px; color:var(--muted); margin-bottom:6px; }
    input, select { width:100%; height:40px; border:1px solid var(--line); border-radius:6px; padding:8px 10px; font-size:15px; background:#fff; }
    .full { grid-column:1 / -1; }
    button, .button { display:inline-flex; align-items:center; justify-content:center; height:42px; border:0; border-radius:6px; background:var(--blue); color:#fff; font-size:15px; font-weight:700; cursor:pointer; text-decoration:none; padding:0 14px; }
    .quick { display:flex; gap:10px; flex-wrap:wrap; }
    .note { margin-top:14px; color:var(--muted); line-height:1.7; }
    @media (max-width: 720px) { form { grid-template-columns:1fr; } header { padding:22px 18px; } main { padding:14px; } }
  </style>
</head>
<body>
  <header>
    <h1>量化交易本地控制台</h1>
    <p>研究、回测、选股、新闻核验和纸面交易辅助。不自动连接券商，不自动下单。</p>
  </header>
  <main>
    <section class="panel">
      <h2>实时盯盘选股</h2>
      <div class="quick">
        <a class="button" href="/watch?strategy=momentum">动量策略</a>
        <a class="button" href="/watch?strategy=breakout">突破策略</a>
        <a class="button" href="/watch?strategy=reversal">反转观察</a>
        <a class="button" href="/watch?strategy=overnight_yang">一夜持股观察</a>
      </div>
      <div class="note">盯盘页会展示热门板块、策略候选、推荐理由、新闻佐证、情绪标签和人工核验链接。“一夜持股观察”只做公开规则的候选过滤，不代表买入建议。</div>
    </section>
    <section class="panel">
      <h2>单票研究报告</h2>
      <form method="post" action="/generate">
        <div><label>股票代码</label><input name="symbol" value="000001" required></div>
        <div><label>资金档位</label><select name="capital_profile"><option value="small-2000">small-2000</option><option value="standard">standard</option></select></div>
        <div><label>开始日期</label><input name="start" value="20240101" required></div>
        <div><label>结束日期</label><input name="end" value="20251231" required></div>
        <div><label>数据源</label><select name="source"><option value="auto">auto</option><option value="akshare-sina">akshare-sina</option><option value="akshare-tencent">akshare-tencent</option><option value="akshare-eastmoney">akshare-eastmoney</option></select></div>
        <div><label>复权方式</label><select name="adjust"><option value="qfq">qfq</option><option value="hfq">hfq</option><option value="">不复权</option></select></div>
        <div><label>当前持仓股数</label><input name="current_position" value="0" inputmode="numeric"></div>
        <div><label>现金覆盖，可留空</label><input name="cash" value="" inputmode="decimal"></div>
        <div class="full"><button type="submit">生成 HTML 报告</button></div>
      </form>
    </section>
  </main>
</body>
</html>
"""


class ConsoleHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._send_html(INDEX_HTML)
            return
        if parsed.path == "/watch":
            params = parse_qs(parsed.query)
            strategy = _value(params, "strategy", "momentum")
            refresh_seconds = int(_value(params, "refresh", "60") or "60")
            result = screen_market(strategy=strategy, limit=10, news_limit=3, quote_timeout=8)
            append_research_log(
                ROOT / "reports" / "research_log.jsonl",
                "screener",
                {
                    "strategy": strategy,
                    "status": result.status,
                    "message": result.message,
                    "candidate_count": len(result.candidates),
                    "steps": steps_to_dicts(result.research_steps),
                },
            )
            self._send_html(render_screener_html(result, refresh_seconds=refresh_seconds))
            return
        if parsed.path == "/report":
            report_path = ROOT / "reports" / "dashboard.html"
            if not report_path.exists():
                self._send_html(_message_page("报告还没有生成", "请先返回控制台生成报告。"), status=404)
                return
            self._send_html(report_path.read_text(encoding="utf-8"))
            return
        self._send_html(_message_page("页面不存在", "请返回控制台。"), status=404)

    def do_POST(self) -> None:
        if self.path != "/generate":
            self._send_html(_message_page("页面不存在", "请返回控制台。"), status=404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        params = parse_qs(self.rfile.read(length).decode("utf-8"))
        try:
            output = ROOT / "reports" / "dashboard.html"
            generate_html_report(
                output_path=output,
                symbol=_value(params, "symbol", "000001"),
                start_date=_value(params, "start", "20240101"),
                end_date=_value(params, "end", "20251231"),
                source=_value(params, "source", "auto"),
                adjust=_value(params, "adjust", "qfq"),
                cache_path=ROOT / "data" / "market_data.sqlite",
                capital_profile=_value(params, "capital_profile", "small-2000"),
                cash=_optional_float(_value(params, "cash", "")),
                current_position=int(_value(params, "current_position", "0") or "0"),
                refresh=False,
            )
        except Exception as exc:
            self._send_html(_message_page("生成失败", html.escape(str(exc))), status=500)
            return
        self.send_response(303)
        self.send_header("Location", "/report")
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        print(f"[local-console] {self.address_string()} - {format % args}")

    def _send_html(self, body: str, status: int = 200) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def main() -> None:
    parser = ArgumentParser(description="启动量化交易本地控制台。")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--open", action="store_true", help="启动后自动打开浏览器")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), ConsoleHandler)
    url = f"http://{args.host}:{args.port}"
    print(f"本地控制台已启动: {url}")
    if args.open:
        webbrowser.open(url)
    server.serve_forever()


def _value(params: dict[str, list[str]], key: str, default: str) -> str:
    values = params.get(key)
    return values[0].strip() if values else default


def _optional_float(value: str) -> float | None:
    return None if value == "" else float(value)


def _message_page(title: str, message: str) -> str:
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><title>{title}</title>
<style>body{{font-family:"Microsoft YaHei","Segoe UI",Arial,sans-serif;background:#f4f7fb;color:#17202a;padding:32px}}a{{color:#2563eb}}</style>
</head><body><h1>{title}</h1><p>{message}</p><p><a href="/">返回控制台</a></p></body></html>"""


if __name__ == "__main__":
    main()
