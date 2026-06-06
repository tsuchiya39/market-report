"""Technical indicator computation and signal generation."""

from typing import Dict, List

import numpy as np
import pandas as pd

import config


def compute_indicators(df: pd.DataFrame) -> Dict[str, float]:
    """Compute technical indicators for the price data.

    Calculates: RSI, moving averages, MACD, Bollinger Bands, volume.

    Args:
        df: DataFrame with 'Close' and 'Volume' columns

    Returns:
        Dict with indicators: latest, prev, change, rsi, ma25, ma75, etc.
    """
    close = df["Close"].squeeze()
    n = len(close)

    # RSI (14)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(config.RSI_PERIOD).mean()
    loss = (-delta.clip(upper=0)).rolling(config.RSI_PERIOD).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs)

    # Moving averages
    ma_short = close.rolling(config.MA_SHORT).mean()
    ma_long = close.rolling(config.MA_LONG).mean()

    # MACD
    ema_fast = close.ewm(span=config.MACD_FAST, adjust=False).mean()
    ema_slow = close.ewm(span=config.MACD_SLOW, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=config.MACD_SIGNAL, adjust=False).mean()

    # Bollinger Bands
    bb_mid = close.rolling(config.BB_PERIOD).mean()
    bb_std = close.rolling(config.BB_PERIOD).std()
    bb_upper = bb_mid + config.BB_STD_DEV * bb_std
    bb_lower = bb_mid - config.BB_STD_DEV * bb_std

    # Volume
    has_volume = _check_volume(df)
    vol = df["Volume"] if has_volume else None
    vol_ma = vol.rolling(config.VOLUME_MA_PERIOD).mean() if has_volume else None

    # Latest values
    latest = close.iloc[-1]
    prev = close.iloc[-2]
    change = latest - prev
    change_pct = change / prev * 100

    return {
        "latest": latest,
        "prev": prev,
        "change": change,
        "change_pct": change_pct,
        "rsi": float(rsi.iloc[-1]),
        "ma25": float(ma_short.iloc[-1]),
        "ma75": float(ma_long.iloc[-1]) if n >= config.MA_LONG else None,
        "macd": float(macd_line.iloc[-1]),
        "signal": float(signal_line.iloc[-1]),
        "macd_prev": float(macd_line.iloc[-2]),
        "signal_prev": float(signal_line.iloc[-2]),
        "bb_upper": float(bb_upper.iloc[-1]),
        "bb_lower": float(bb_lower.iloc[-1]),
        "bb_mid": float(bb_mid.iloc[-1]),
        "vol_latest": float(vol.iloc[-1]) if has_volume else None,
        "vol_ma20": float(vol_ma.iloc[-1]) if has_volume else None,
    }


def _check_volume(df: pd.DataFrame) -> bool:
    """Check if volume data is available and non-zero."""
    if "Volume" not in df.columns:
        return False
    vol_col = df["Volume"]
    if not hasattr(vol_col, "iloc"):
        return False
    vol_val = vol_col.iloc[-1]
    return isinstance(vol_val, (int, float, np.number)) and vol_val > 0


def generate_evidence(indicators: Dict, asset_name: str) -> Dict[str, List[str]]:
    """Generate bullish and bearish trading signals from technical indicators.

    Args:
        indicators: Dict of computed technical indicators
        asset_name: Name of the asset

    Returns:
        Dict with keys "bullish" and "bearish" containing signal strings
    """
    bullish, bearish = [], []
    price = indicators["latest"]

    # RSI signals
    _add_rsi_signals(bullish, bearish, indicators["rsi"])

    # Moving average signals
    _add_ma_signals(bullish, bearish, price, indicators)

    # MACD signals
    _add_macd_signals(bullish, bearish, indicators)

    # Bollinger Band signals
    _add_bb_signals(bullish, bearish, price, indicators)

    # Volume signals
    _add_volume_signals(bullish, bearish, indicators)

    return {"bullish": bullish, "bearish": bearish}


def _add_rsi_signals(bullish: List, bearish: List, rsi: float):
    """Add RSI-based signals."""
    if np.isnan(rsi):
        return
    if rsi >= 70:
        bearish.append(f"RSI {rsi:.1f} — 過買い水準（70超）。短期的な調整リスクあり。")
    elif rsi <= 30:
        bullish.append(f"RSI {rsi:.1f} — 過売り水準（30未満）。反発の可能性あり。")
    elif rsi >= 55:
        bullish.append(f"RSI {rsi:.1f} — 強気ゾーン（55-70）。上昇モメンタム継続中。")
    elif rsi <= 45:
        bearish.append(f"RSI {rsi:.1f} — 弱気ゾーン（30-45）。下落圧力が続いている。")


def _add_ma_signals(bullish: List, bearish: List, price: float, ind: Dict):
    """Add moving average-based signals."""
    ma25 = ind["ma25"]
    ma75 = ind["ma75"]

    if not np.isnan(ma25):
        if price > ma25:
            bullish.append(f"価格（{price:,.2f}）が25日移動平均線（{ma25:,.2f}）を上回っている。短期トレンドは強気。")
        else:
            bearish.append(f"価格（{price:,.2f}）が25日移動平均線（{ma25:,.2f}）を下回っている。短期トレンドは弱気。")

    if ma75 is not None and not np.isnan(ma75):
        if price > ma75:
            bullish.append(f"価格が75日移動平均線（{ma75:,.2f}）を上回っており、中長期トレンドは強気。")
        else:
            bearish.append(f"価格が75日移動平均線（{ma75:,.2f}）を下回っており、中長期トレンドは弱気。")


def _add_macd_signals(bullish: List, bearish: List, ind: Dict):
    """Add MACD-based signals."""
    macd = ind["macd"]
    signal = ind["signal"]
    macd_prev = ind["macd_prev"]
    signal_prev = ind["signal_prev"]

    if any(np.isnan(v) for v in [macd, signal, macd_prev, signal_prev]):
        return

    if macd > signal and macd_prev <= signal_prev:
        bullish.append("MACDがシグナルラインをゴールデンクロス。買いシグナル発生。")
    elif macd < signal and macd_prev >= signal_prev:
        bearish.append("MACDがシグナルラインをデッドクロス。売りシグナル発生。")
    elif macd > signal:
        bullish.append(f"MACD（{macd:+.2f}）はシグナル（{signal:.2f}）を上回っており、強気継続。")
    else:
        bearish.append(f"MACD（{macd:+.2f}）はシグナル（{signal:.2f}）を下回っており、弱気継続。")


def _add_bb_signals(bullish: List, bearish: List, price: float, ind: Dict):
    """Add Bollinger Band-based signals."""
    bb_u = ind["bb_upper"]
    bb_l = ind["bb_lower"]
    bb_m = ind["bb_mid"]

    if any(np.isnan(v) for v in [bb_u, bb_l, bb_m]):
        return

    band_width = bb_u - bb_l
    if band_width > 0:
        upper_dist_pct = (bb_u - price) / band_width * 100
        lower_dist_pct = (price - bb_l) / band_width * 100

        if upper_dist_pct < 10:
            bearish.append(f"ボリンジャーバンド上限（{bb_u:,.2f}）に接近。過熱感あり。")
        elif lower_dist_pct < 10:
            bullish.append(f"ボリンジャーバンド下限（{bb_l:,.2f}）付近。反発期待。")

    if price > bb_m:
        bullish.append(f"ボリンジャーバンド中央線（{bb_m:,.2f}）を上回っており、強気優勢。")
    else:
        bearish.append(f"ボリンジャーバンド中央線（{bb_m:,.2f}）を下回っており、弱気優勢。")


def _add_volume_signals(bullish: List, bearish: List, ind: Dict):
    """Add volume-based signals."""
    vol_l = ind["vol_latest"]
    vol_ma = ind["vol_ma20"]

    if not vol_l or not vol_ma or np.isnan(vol_ma) or vol_ma == 0:
        return

    ratio = vol_l / vol_ma
    if ratio > 1.5:
        bullish.append(f"出来高が20日平均の {ratio:.1f}倍。市場参加者の関心が急増。")
    elif ratio < 0.5:
        bearish.append(f"出来高が20日平均の {ratio:.1f}倍と低調。トレンドの信頼性に疑問。")


def chart_data(df: pd.DataFrame) -> Dict[str, list]:
    """Extract last 30 days of price data for charting.

    Args:
        df: DataFrame with price data

    Returns:
        Dict with "labels" (dates) and "values" (prices)
    """
    tail = df["Close"].tail(config.MAX_CHART_DAYS).squeeze()
    labels = [d.strftime("%m/%d") for d in tail.index]
    values = [round(float(v), 2) for v in tail.values]
    return {"labels": labels, "values": values}
