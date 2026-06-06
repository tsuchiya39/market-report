#!/usr/bin/env python3
"""Fetch market data and generate index.html report."""

import json
import os
import traceback
from datetime import datetime, timezone, timedelta
from urllib.parse import urljoin

import feedparser
import numpy as np
import pandas as pd
import pytz
import requests
import yfinance as yf

JST = pytz.timezone("Asia/Tokyo")
NOW_JST = datetime.now(JST).strftime("%Y-%m-%d %H:%M JST")


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def fetch_yfinance(ticker: str, period: str = "3mo") -> pd.DataFrame:
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    df = df.dropna()
    return df


def fetch_btc() -> pd.DataFrame:
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": "90", "interval": "daily"}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    prices = data["prices"]          # [[timestamp_ms, price], ...]
    volumes = {int(v[0]): v[1] for v in data["total_volumes"]}
    rows = []
    for ts_ms, price in prices:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        rows.append({"Date": dt, "Close": price, "Volume": volumes.get(int(ts_ms), 0)})
    df = pd.DataFrame(rows).set_index("Date").sort_index()
    # CoinGecko sometimes returns the same day twice; keep last
    df = df[~df.index.duplicated(keep="last")]
    return df



# ---------------------------------------------------------------------------
# News fetching
# ---------------------------------------------------------------------------

def fetch_news(asset_name: str, ticker: str) -> list:
    """Fetch relevant news for the asset. Returns list of dicts: {title, url, date}"""
    rss_feeds = {
        "日経225": [
            "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja&topic=b",  # Google News Japan Business
            "https://news.google.com/rss/headlines?hl=ja&gl=JP&ceid=JP:ja",  # Google News Japan
        ],
        "S&P 500": [
            # Yahoo Finance は US market 専門で日本語ニュースソースなし
            # S&P 500 は米国市場指数のため英語ニュースが最適
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC",
        ],
        "BTC/USD": [
            "https://www.coindeskjapan.com/feed/",  # CoinDesk Japan (日本語)
            "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD",  # Yahoo Finance (英語)
            "https://cointelegraph.com/feed",  # CoinTelegraph (英語)
        ],
    }

    keywords = {
        "日経225": ["株", "相場", "市場"],
        "BTC/USD": ["bitcoin", "btc"],
    }

    news_items = []
    asset_keywords = keywords.get(asset_name, [])

    for feed_url in rss_feeds.get(asset_name, []):
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:40]:
                try:
                    title = entry.get("title", "No title")
                    link = entry.get("link", "")
                    pub_date = entry.get("published", "")

                    # Filter by keywords only for non-Nikkei feeds
                    if asset_keywords and "google" in feed_url.lower() and asset_name != "日経225":
                        if not any(kw.lower() in title.lower() for kw in asset_keywords):
                            continue

                    if title and link:
                        news_items.append({
                            "title": title[:100],
                            "url": link,
                            "date": pub_date,
                        })
                        if len(news_items) >= 8:
                            break
                except Exception:
                    continue

            if len(news_items) >= 8:
                break
        except Exception:
            continue

    return news_items[:8]


# ---------------------------------------------------------------------------
# Technical indicators
# ---------------------------------------------------------------------------

def compute_indicators(df: pd.DataFrame) -> dict:
    close = df["Close"].squeeze()  # Ensure it's a Series
    n = len(close)

    # RSI 14
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)

    # Moving averages
    ma25 = close.rolling(25).mean()
    ma75 = close.rolling(75).mean()

    # MACD (12/26/9)
    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    macd_line = ema12 - ema26
    signal_line = macd_line.ewm(span=9, adjust=False).mean()

    # Bollinger Bands (20, 2σ)
    bb_mid = close.rolling(20).mean()
    bb_std = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    # Volume (skip if all-zero, e.g. BTC doesn't always have it)
    has_volume = False
    if "Volume" in df.columns:
        vol_col = df["Volume"]
        if hasattr(vol_col, "iloc"):
            vol_val = vol_col.iloc[-1]
            if isinstance(vol_val, (int, float, np.number)):
                has_volume = vol_val > 0
    if has_volume:
        vol = df["Volume"]
        vol_ma20 = vol.rolling(20).mean()
    else:
        vol = None
        vol_ma20 = None

    latest = close.iloc[-1]
    prev = close.iloc[-2]
    change = latest - prev
    change_pct = change / prev * 100

    return dict(
        latest=latest, prev=prev, change=change, change_pct=change_pct,
        rsi=float(rsi.iloc[-1]),
        ma25=float(ma25.iloc[-1]), ma75=float(ma75.iloc[-1]) if n >= 75 else None,
        macd=float(macd_line.iloc[-1]), signal=float(signal_line.iloc[-1]),
        macd_prev=float(macd_line.iloc[-2]), signal_prev=float(signal_line.iloc[-2]),
        bb_upper=float(bb_upper.iloc[-1]), bb_lower=float(bb_lower.iloc[-1]),
        bb_mid=float(bb_mid.iloc[-1]),
        vol_latest=float(vol.iloc[-1]) if has_volume else None,
        vol_ma20=float(vol_ma20.iloc[-1]) if has_volume else None,
    )


def generate_evidence(ind: dict, asset_name: str) -> dict:
    bullish, bearish = [], []
    p = ind["latest"]

    # RSI
    rsi = ind["rsi"]
    if not np.isnan(rsi):
        if rsi >= 70:
            bearish.append(f"RSI {rsi:.1f} — 過買い水準（70超）。短期的な調整リスクあり。")
        elif rsi <= 30:
            bullish.append(f"RSI {rsi:.1f} — 過売り水準（30未満）。反発の可能性あり。")
        elif rsi >= 55:
            bullish.append(f"RSI {rsi:.1f} — 強気ゾーン（55-70）。上昇モメンタム継続中。")
        elif rsi <= 45:
            bearish.append(f"RSI {rsi:.1f} — 弱気ゾーン（30-45）。下落圧力が続いている。")

    # Moving averages
    ma25 = ind["ma25"]
    ma75 = ind["ma75"]
    if not np.isnan(ma25):
        if p > ma25:
            bullish.append(f"価格（{p:,.2f}）が25日移動平均線（{ma25:,.2f}）を上回っている。短期トレンドは強気。")
        else:
            bearish.append(f"価格（{p:,.2f}）が25日移動平均線（{ma25:,.2f}）を下回っている。短期トレンドは弱気。")
    if ma75 is not None and not np.isnan(ma75):
        if p > ma75:
            bullish.append(f"価格が75日移動平均線（{ma75:,.2f}）を上回っており、中長期トレンドは強気。")
        else:
            bearish.append(f"価格が75日移動平均線（{ma75:,.2f}）を下回っており、中長期トレンドは弱気。")

    # MACD
    macd, signal = ind["macd"], ind["signal"]
    macd_prev, signal_prev = ind["macd_prev"], ind["signal_prev"]
    if not any(np.isnan(v) for v in [macd, signal, macd_prev, signal_prev]):
        if macd > signal and macd_prev <= signal_prev:
            bullish.append("MACDがシグナルラインをゴールデンクロス。買いシグナル発生。")
        elif macd < signal and macd_prev >= signal_prev:
            bearish.append("MACDがシグナルラインをデッドクロス。売りシグナル発生。")
        elif macd > signal:
            bullish.append(f"MACD（{macd:+.2f}）はシグナル（{signal:.2f}）を上回っており、強気継続。")
        else:
            bearish.append(f"MACD（{macd:+.2f}）はシグナル（{signal:.2f}）を下回っており、弱気継続。")

    # Bollinger Bands
    bb_u, bb_l, bb_m = ind["bb_upper"], ind["bb_lower"], ind["bb_mid"]
    if not any(np.isnan(v) for v in [bb_u, bb_l, bb_m]):
        band_width = bb_u - bb_l
        upper_dist_pct = (bb_u - p) / band_width * 100
        lower_dist_pct = (p - bb_l) / band_width * 100
        if upper_dist_pct < 10:
            bearish.append(f"ボリンジャーバンド上限（{bb_u:,.2f}）に接近。過熱感あり。")
        elif lower_dist_pct < 10:
            bullish.append(f"ボリンジャーバンド下限（{bb_l:,.2f}）付近。反発期待。")
        if p > bb_m:
            bullish.append(f"ボリンジャーバンド中央線（{bb_m:,.2f}）を上回っており、強気優勢。")
        else:
            bearish.append(f"ボリンジャーバンド中央線（{bb_m:,.2f}）を下回っており、弱気優勢。")

    # Volume
    vol_l = ind["vol_latest"]
    vol_ma = ind["vol_ma20"]
    if vol_l and vol_ma and not np.isnan(vol_ma) and vol_ma > 0:
        ratio = vol_l / vol_ma
        if ratio > 1.5:
            bullish.append(f"出来高が20日平均の {ratio:.1f}倍。市場参加者の関心が急増。")
        elif ratio < 0.5:
            bearish.append(f"出来高が20日平均の {ratio:.1f}倍と低調。トレンドの信頼性に疑問。")

    return {"bullish": bullish, "bearish": bearish}


# ---------------------------------------------------------------------------
# Chart data (last 30 days)
# ---------------------------------------------------------------------------

def chart_data(df: pd.DataFrame) -> dict:
    tail = df["Close"].tail(30).squeeze()
    labels = [d.strftime("%m/%d") for d in tail.index]
    values = [round(float(v), 2) for v in tail.values]
    return {"labels": labels, "values": values}


# ---------------------------------------------------------------------------
# HTML generation
# ---------------------------------------------------------------------------

HTML_TEMPLATE = """<!DOCTYPE html>
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

CARD_TEMPLATE = """    <div class="card">
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


def format_price(val: float, is_btc: bool = False) -> str:
    if is_btc:
        return f"${val:,.0f}"
    return f"{val:,.2f}"


def build_html(assets: list) -> str:
    cards_html = []
    chart_configs = []

    for a in assets:
        ind = a["indicators"]
        ev = a["evidence"]
        cd = a["chart"]
        news = a.get("news", [])
        is_btc = a["name"] == "BTC/USD"

        price_str = format_price(ind["latest"], is_btc)
        change_str = f"{ind['change']:+,.2f}" if not is_btc else f"${ind['change']:+,.0f}"
        pct_str = f"{ind['change_pct']:+.2f}"
        dir_class = "up" if ind["change"] >= 0 else "down"

        bull_items = "".join(f'<li class="ev-bull">{e}</li>' for e in ev["bullish"]) or '<li class="ev-none">シグナルなし</li>'
        bear_items = "".join(f'<li class="ev-bear">{e}</li>' for e in ev["bearish"]) or '<li class="ev-none">シグナルなし</li>'

        news_items = ""
        if news:
            for item in news[:8]:
                title = item.get("title", "No title")[:80]
                url = item.get("url", "#")
                news_items += f'<li class="news-item"><a href="{url}" target="_blank" rel="noopener">{title}</a></li>'
        else:
            news_items = '<li class="news-item" style="border-left-color: #94a3b8; background: rgba(148,163,184,0.08);">ニュースを取得中...</li>'

        chart_id = f"chart_{a['ticker'].replace('^','').replace('/','')}"
        chart_configs.append({"id": chart_id, "labels": cd["labels"], "values": cd["values"]})

        cards_html.append(CARD_TEMPLATE.format(
            icon=a["icon"], name=a["name"],
            price_str=price_str, change_str=change_str, pct_str=pct_str,
            dir_class=dir_class, chart_id=chart_id,
            bull_items=bull_items, bear_items=bear_items,
            news_items=news_items,
        ))

    return HTML_TEMPLATE.format(
        updated=NOW_JST,
        cards="\n".join(cards_html),
        chart_configs=json.dumps(chart_configs, ensure_ascii=False),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

ASSETS = [
    {"ticker": "^N225",  "name": "日経225",  "icon": "🗼", "btc": False},
    {"ticker": "^GSPC",  "name": "S&P 500",  "icon": "🇺🇸", "btc": False},
    {"ticker": "BTC/USD","name": "BTC/USD",  "icon": "₿",  "btc": True},
]


def main():
    results = []
    for a in ASSETS:
        try:
            print(f"Fetching {a['name']} ...")
            if a["btc"]:
                df = fetch_btc()
            else:
                df = fetch_yfinance(a["ticker"])
            ind = compute_indicators(df)
            ev = generate_evidence(ind, a["name"])
            cd = chart_data(df)
            news = fetch_news(a["name"], a["ticker"])
            results.append({**a, "indicators": ind, "evidence": ev, "chart": cd, "news": news})
            print(f"  -> {a['name']}: {ind['latest']:,.2f} ({ind['change_pct']:+.2f}%) | {len(news)} news items")
        except Exception:
            print(f"ERROR fetching {a['name']}:")
            traceback.print_exc()

    if not results:
        print("All fetches failed. Keeping existing index.html.")
        return

    html = build_html(results)
    out_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\nGenerated: {out_path}")


if __name__ == "__main__":
    main()
