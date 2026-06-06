"""Configuration for Market Daily Report."""

# Asset configurations
ASSETS = [
    {"ticker": "^N225", "name": "日経225", "icon": "🗼", "btc": False},
    {"ticker": "^GSPC", "name": "S&P 500", "icon": "🇺🇸", "btc": False},
    {"ticker": "BTC/USD", "name": "BTC/USD", "icon": "₿", "btc": True},
]

# News RSS feed configuration
NEWS_FEEDS = {
    "日経225": [
        "https://news.google.com/rss?hl=ja&gl=JP&ceid=JP:ja&topic=b",
        "https://news.google.com/rss/headlines?hl=ja&gl=JP&ceid=JP:ja",
    ],
    "S&P 500": [
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=^GSPC",
    ],
    "BTC/USD": [
        "https://www.coindeskjapan.com/feed/",
        "https://feeds.finance.yahoo.com/rss/2.0/headline?s=BTC-USD",
        "https://cointelegraph.com/feed",
    ],
}

# Keyword filters for news matching (mainly for Google News)
NEWS_KEYWORDS = {
    "日経225": ["株", "相場", "市場"],
    "BTC/USD": ["bitcoin", "btc"],
}

# Data fetch parameters
DATA_PERIOD = "3mo"
BTC_DAYS = 90

# Technical indicator parameters
RSI_PERIOD = 14
MA_SHORT = 25
MA_LONG = 75
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9
BB_PERIOD = 20
BB_STD_DEV = 2
VOLUME_MA_PERIOD = 20

# News parameters
NEWS_MAX_ITEMS = 8
NEWS_ENTRIES_PER_FEED = 40

# HTML parameters
CHART_HEIGHT = 180
MAX_TITLE_LENGTH = 100
MAX_CHART_DAYS = 30
