"""Data fetching from financial APIs and news sources."""

from datetime import datetime, timezone
from typing import Dict, List

import feedparser
import pandas as pd
import requests
import yfinance as yf

import config


def fetch_yfinance(ticker: str, period: str = config.DATA_PERIOD) -> pd.DataFrame:
    """Fetch price data from Yahoo Finance.

    Args:
        ticker: Stock ticker symbol (e.g., "^N225")
        period: Data period (default: "3mo")

    Returns:
        DataFrame with price data, indexed by date
    """
    df = yf.download(ticker, period=period, auto_adjust=True, progress=False)
    return df.dropna()


def fetch_btc() -> pd.DataFrame:
    """Fetch Bitcoin price data from CoinGecko API.

    Returns:
        DataFrame with BTC/USD price and volume, indexed by date
    """
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": str(config.BTC_DAYS), "interval": "daily"}
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()

    data = response.json()
    prices = data["prices"]
    volumes = {int(v[0]): v[1] for v in data["total_volumes"]}

    rows = []
    for ts_ms, price in prices:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        rows.append({"Date": dt, "Close": price, "Volume": volumes.get(int(ts_ms), 0)})

    df = pd.DataFrame(rows).set_index("Date").sort_index()
    return df[~df.index.duplicated(keep="last")]


def fetch_news(asset_name: str) -> List[Dict[str, str]]:
    """Fetch news from RSS feeds for the given asset.

    Args:
        asset_name: Name of the asset (e.g., "日経225", "BTC/USD")

    Returns:
        List of dicts with keys: title, url, date (max 8 items)
    """
    news_items = []
    asset_keywords = config.NEWS_KEYWORDS.get(asset_name, [])

    for feed_url in config.NEWS_FEEDS.get(asset_name, []):
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries[:config.NEWS_ENTRIES_PER_FEED]:
                title = entry.get("title", "No title")
                link = entry.get("link", "")
                pub_date = entry.get("published", "")

                # Skip if keyword filter is needed and not matched
                if asset_keywords and "google" in feed_url.lower() and asset_name != "日経225":
                    if not any(kw.lower() in title.lower() for kw in asset_keywords):
                        continue

                if title and link:
                    news_items.append({
                        "title": title[:config.MAX_TITLE_LENGTH],
                        "url": link,
                        "date": pub_date,
                    })
                    if len(news_items) >= config.NEWS_MAX_ITEMS:
                        break

            if len(news_items) >= config.NEWS_MAX_ITEMS:
                break
        except Exception:
            continue

    return news_items[:config.NEWS_MAX_ITEMS]
