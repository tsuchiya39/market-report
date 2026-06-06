"""HTML report generation."""

import json
from datetime import datetime
from typing import Dict, List

import pytz

import config

JST = pytz.timezone("Asia/Tokyo")


def format_price(value: float, is_btc: bool = False) -> str:
    """Format price with appropriate currency symbol and decimals."""
    if is_btc:
        return f"${value:,.0f}"
    return f"{value:,.2f}"


def _get_html_template() -> str:
    """Get base HTML template."""
    return """<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Market Daily Report</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --card: #1a1d27; --border: #2a2d3a;
    --text: #e2e8f0; --muted: #94a3b8; --green: #4ade80;
    --red: #f87171; --blue: #60a5fa; --accent: #7c3aed;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; min-height: 100vh; }}
  header {{ background: linear-gradient(135deg, #1e1b4b 0%, #0f1117 100%); padding: 2rem 1rem; text-align: center; border-bottom: 1px solid var(--border); }}
  header h1 {{ font-size: clamp(1.4rem, 4vw, 2rem); font-weight: 700; letter-spacing: 0.05em; }}
  header p {{ color: var(--muted); margin-top: 0.4rem; font-size: 0.9rem; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 1.5rem 1rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 1.5rem; }}
  .card {{ background: var(--card); border: 1px solid var(--border); border-radius: 1rem; padding: 1.5rem; }}
  .card-title {{ font-size: 1.1rem; font-weight: 600; margin-bottom: 1rem; display: flex; align-items: center; gap: 0.5rem; }}
  .price-row {{ display: flex; align-items: baseline; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem; }}
  .price {{ font-size: clamp(1.5rem, 4vw, 2rem); font-weight: 700; }}
  .change {{ font-size: 1rem; font-weight: 600; padding: 0.2rem 0.6rem; border-radius: 0.4rem; }}
  .up {{ color: var(--green); background: rgba(74,222,128,0.12); }}
  .down {{ color: var(--red); background: rgba(248,113,113,0.12); }}
  .chart-wrap {{ position: relative; height: 180px; margin-bottom: 1.25rem; }}
  .evidence {{ margin-top: 0.5rem; }}
  .evidence h3 {{ font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-bottom: 0.5rem; }}
  .ev-list {{ list-style: none; display: flex; flex-direction: column; gap: 0.4rem; }}
  .ev-list li {{ font-size: 0.82rem; padding: 0.45rem 0.7rem; border-radius: 0.4rem; line-height: 1.4; }}
  .ev-bull {{ background: rgba(74,222,128,0.08); border-left: 3px solid var(--green); }}
  .ev-bear {{ background: rgba(248,113,113,0.08); border-left: 3px solid var(--red); }}
  .ev-none {{ color: var(--muted); font-style: italic; }}
  .news-section {{ margin-top: 1.25rem; padding-top: 1.25rem; border-top: 1px solid var(--border); }}
  .news-section h3 {{ font-size: 0.8rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-bottom: 0.5rem; }}
  .news-list {{ list-style: none; display: flex; flex-direction: column; gap: 0.6rem; }}
  .news-item {{ font-size: 0.75rem; padding: 0.6rem 0.7rem; border-radius: 0.4rem; background: rgba(96,165,250,0.08); border-left: 3px solid var(--blue); }}
  .news-item a {{ color: var(--blue); text-decoration: none; font-weight: 500; }}
  .news-item a:hover {{ text-decoration: underline; }}
  .news-item .date {{ color: var(--muted); font-size: 0.7rem; margin-top: 0.2rem; display: block; }}
  footer {{ text-align: center; padding: 2rem 1rem; color: var(--muted); font-size: 0.8rem; border-top: 1px solid var(--border); }}
  @media (max-width: 480px) {{ .card {{ padding: 1rem; }} }}
</style>
</head>
<body>
<header>
  <h1>📈 Market Daily Report</h1>
  <p>最終更新: {updated}</p>
</header>
<div class="container">
  <div class="grid">
{cards}
  </div>
</div>
<footer>Powered by yfinance &amp; CoinGecko &nbsp;|&nbsp; Data for informational purposes only.</footer>
<script>
const chartConfigs = {chart_configs};
chartConfigs.forEach(function(cfg) {{
  const ctx = document.getElementById(cfg.id).getContext('2d');
  const isUp = cfg.values[cfg.values.length - 1] >= cfg.values[0];
  const color = isUp ? '#4ade80' : '#f87171';
  new Chart(ctx, {{
    type: 'line',
    data: {{
      labels: cfg.labels,
      datasets: [{{ data: cfg.values, borderColor: color, borderWidth: 2,
        pointRadius: 0, fill: true,
        backgroundColor: isUp ? 'rgba(74,222,128,0.06)' : 'rgba(248,113,113,0.06)',
        tension: 0.3 }}]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      plugins: {{ legend: {{ display: false }}, tooltip: {{ mode: 'index', intersect: false }} }},
      scales: {{
        x: {{ ticks: {{ color: '#94a3b8', maxTicksLimit: 6, font: {{ size: 10 }} }}, grid: {{ color: '#2a2d3a' }} }},
        y: {{ ticks: {{ color: '#94a3b8', font: {{ size: 10 }} }}, grid: {{ color: '#2a2d3a' }} }}
      }}
    }}
  }});
}});
</script>
</body>
</html>"""


def _get_card_template() -> str:
    """Get card HTML template."""
    return """    <div class="card">
      <div class="card-title">{icon} {name}</div>
      <div class="price-row">
        <span class="price">{price_str}</span>
        <span class="change {dir_class}">{change_str} ({pct_str}%)</span>
      </div>
      <div class="chart-wrap"><canvas id="{chart_id}"></canvas></div>
      <div class="evidence">
        <h3>🟢 強気シグナル</h3>
        <ul class="ev-list">{bull_items}</ul>
        <h3 style="margin-top:0.75rem">🔴 弱気シグナル</h3>
        <ul class="ev-list">{bear_items}</ul>
      </div>
      <div class="news-section">
        <h3>📰 関連ニュース</h3>
        <ul class="news-list">{news_items}</ul>
      </div>
    </div>"""


def build_html(assets: List[Dict]) -> str:
    """Build complete HTML report from asset data.

    Args:
        assets: List of asset dicts with indicators, evidence, chart, news

    Returns:
        HTML string ready for writing to file
    """
    now_jst = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")
    cards_html = []
    chart_configs = []

    card_template = _get_card_template()

    for asset in assets:
        ind = asset["indicators"]
        ev = asset["evidence"]
        chart = asset["chart"]
        news = asset.get("news", [])
        is_btc = asset["name"] == "BTC/USD"

        # Format price and changes
        price_str = format_price(ind["latest"], is_btc)
        change_str = f"{ind['change']:+,.2f}" if not is_btc else f"${ind['change']:+,.0f}"
        pct_str = f"{ind['change_pct']:+.2f}"
        dir_class = "up" if ind["change"] >= 0 else "down"

        # Generate signal HTML
        bull_items = "".join(
            f'<li class="ev-bull">{e}</li>' for e in ev["bullish"]
        ) or '<li class="ev-none">シグナルなし</li>'
        bear_items = "".join(
            f'<li class="ev-bear">{e}</li>' for e in ev["bearish"]
        ) or '<li class="ev-none">シグナルなし</li>'

        # Generate news HTML
        news_items = ""
        if news:
            for item in news[:8]:
                title = item.get("title", "No title")[:80]
                url = item.get("url", "#")
                news_items += f'<li class="news-item"><a href="{url}" target="_blank" rel="noopener">{title}</a></li>'
        else:
            news_items = '<li class="news-item" style="border-left-color: #94a3b8; background: rgba(148,163,184,0.08);">ニュースを取得中...</li>'

        # Add chart data
        chart_id = f"chart_{asset['ticker'].replace('^','').replace('/','')}"
        chart_configs.append({
            "id": chart_id,
            "labels": chart["labels"],
            "values": chart["values"],
        })

        # Build card HTML
        cards_html.append(card_template.format(
            icon=asset["icon"],
            name=asset["name"],
            price_str=price_str,
            change_str=change_str,
            pct_str=pct_str,
            dir_class=dir_class,
            chart_id=chart_id,
            bull_items=bull_items,
            bear_items=bear_items,
            news_items=news_items,
        ))

    html_template = _get_html_template()
    return html_template.format(
        updated=now_jst,
        cards="\n".join(cards_html),
        chart_configs=json.dumps(chart_configs, ensure_ascii=False),
    )
