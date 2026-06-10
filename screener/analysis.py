"""
analysis.py
Technical analysis and stock screening filters.

Each strategy is a standalone function that takes the full data dict
and returns a list of result dicts — easy to add / remove strategies.

Usage:
    from screener.analysis import screen_stocks
    selected = screen_stocks(data)
"""

import logging
import pandas as pd
import numpy as np
from typing import Optional

log = logging.getLogger(__name__)


# ── Indicator helpers ──────────────────────────────────────────────────────────

def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index."""
    delta = series.diff()
    gain = delta.clip(lower=0).ewm(com=period - 1, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(com=period - 1, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def compute_ema(series: pd.Series, period: int) -> pd.Series:
    """Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def compute_sma(series: pd.Series, period: int) -> pd.Series:
    """Simple Moving Average."""
    return series.rolling(window=period).mean()


def compute_macd(series: pd.Series, fast=12, slow=26, signal=9):
    """MACD line, signal line, and histogram."""
    ema_fast = compute_ema(series, fast)
    ema_slow = compute_ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = compute_ema(macd_line, signal)
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def compute_bollinger_bands(series: pd.Series, period=20, std_dev=2):
    """Upper band, middle band (SMA), lower band."""
    sma = compute_sma(series, period)
    std = series.rolling(window=period).std()
    upper = sma + std_dev * std
    lower = sma - std_dev * std
    return upper, sma, lower


def compute_atr(df: pd.DataFrame, period=14) -> pd.Series:
    """Average True Range (volatility measure)."""
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.ewm(com=period - 1, adjust=False).mean()


# ── Individual strategies ──────────────────────────────────────────────────────

def strategy_rsi_oversold(df: pd.DataFrame, symbol: str) -> Optional[dict]:
    """
    RSI Oversold + Volume Spike
    Signal: RSI < 35 AND today's volume > 1.5x the 20-day average.
    Best for: spotting potential reversals after a sell-off.
    """
    if len(df) < 20:
        return None

    df = df.copy()
    df["rsi"] = compute_rsi(df["Close"])
    df["vol_ma20"] = compute_sma(df["Volume"], 20)

    row = df.iloc[-1]
    rsi = row["rsi"]
    vol_ratio = row["Volume"] / row["vol_ma20"] if row["vol_ma20"] > 0 else 0

    if rsi < 35 and vol_ratio > 1.5:
        return {
            "symbol": symbol,
            "strategy": "RSI Oversold + Volume Spike",
            "close": round(row["Close"], 2),
            "rsi": round(rsi, 2),
            "vol_ratio": round(vol_ratio, 2),
            "signal": "BUY",
        }
    return None


def strategy_ema_crossover(df: pd.DataFrame, symbol: str) -> Optional[dict]:
    """
    EMA 9 / 21 Golden Cross
    Signal: EMA9 crosses above EMA21 in the last 2 candles.
    Best for: catching early trend starts.
    """
    if len(df) < 30:
        return None

    df = df.copy()
    df["ema9"] = compute_ema(df["Close"], 9)
    df["ema21"] = compute_ema(df["Close"], 21)

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    # Golden cross: EMA9 crossed above EMA21
    crossed_above = prev["ema9"] <= prev["ema21"] and curr["ema9"] > curr["ema21"]

    if crossed_above:
        return {
            "symbol": symbol,
            "strategy": "EMA 9/21 Golden Cross",
            "close": round(curr["Close"], 2),
            "ema9": round(curr["ema9"], 2),
            "ema21": round(curr["ema21"], 2),
            "signal": "BUY",
        }
    return None


def strategy_macd_crossover(df: pd.DataFrame, symbol: str) -> Optional[dict]:
    """
    MACD Bullish Crossover
    Signal: MACD line crosses above signal line yesterday→today.
    Best for: momentum confirmation in trending stocks.
    """
    if len(df) < 40:
        return None

    df = df.copy()
    macd, signal, hist = compute_macd(df["Close"])
    df["macd"] = macd
    df["signal"] = signal
    df["hist"] = hist

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    crossed_above = prev["macd"] <= prev["signal"] and curr["macd"] > curr["signal"]

    if crossed_above:
        return {
            "symbol": symbol,
            "strategy": "MACD Bullish Crossover",
            "close": round(curr["Close"], 2),
            "macd": round(curr["macd"], 2),
            "signal_val": round(curr["signal"], 2),
            "histogram": round(curr["hist"], 2),
            "signal": "BUY",
        }
    return None


def strategy_bollinger_bounce(df: pd.DataFrame, symbol: str) -> Optional[dict]:
    """
    Bollinger Band Lower Bounce
    Signal: Previous candle touched/breached lower band AND
            current candle closes back inside the band.
    Best for: mean-reversion plays in range-bound stocks.
    """
    if len(df) < 25:
        return None

    df = df.copy()
    upper, mid, lower = compute_bollinger_bands(df["Close"])
    df["bb_upper"] = upper
    df["bb_mid"] = mid
    df["bb_lower"] = lower

    prev = df.iloc[-2]
    curr = df.iloc[-1]

    touched_lower = prev["Close"] <= prev["bb_lower"]
    bounced_back = curr["Close"] > curr["bb_lower"]

    if touched_lower and bounced_back:
        band_width = curr["bb_upper"] - curr["bb_lower"]
        pct_b = (curr["Close"] - curr["bb_lower"]) / band_width if band_width > 0 else 0

        return {
            "symbol": symbol,
            "strategy": "Bollinger Band Bounce",
            "close": round(curr["Close"], 2),
            "bb_lower": round(curr["bb_lower"], 2),
            "bb_upper": round(curr["bb_upper"], 2),
            "pct_b": round(pct_b, 3),
            "signal": "BUY",
        }
    return None


def strategy_52w_breakout(df: pd.DataFrame, symbol: str) -> Optional[dict]:
    """
    52-Week High Breakout
    Signal: Today's close is the highest close in the last 252 trading days.
    Best for: momentum / breakout traders.
    Requires at least ~250 days of data (fetch with period='1y' or '2y').
    """
    if len(df) < 50:
        return None

    lookback = min(252, len(df))
    window = df["Close"].iloc[-lookback:]
    curr_close = df["Close"].iloc[-1]
    prev_high = window.iloc[:-1].max()

    if curr_close > prev_high:
        return {
            "symbol": symbol,
            "strategy": "52-Week High Breakout",
            "close": round(curr_close, 2),
            "prev_52w_high": round(prev_high, 2),
            "breakout_pct": round((curr_close / prev_high - 1) * 100, 2),
            "signal": "BUY",
        }
    return None


# ── Master screener ────────────────────────────────────────────────────────────

# Add or remove strategies here — each function must have signature:
#   (df: pd.DataFrame, symbol: str) -> Optional[dict]
STRATEGIES = [
    strategy_rsi_oversold,
    strategy_ema_crossover,
    strategy_macd_crossover,
    strategy_bollinger_bounce,
    strategy_52w_breakout,
]


def screen_stocks(data: dict) -> list:
    """
    Run all strategies against the full data dict.

    Returns a flat list of result dicts, one entry per (stock, strategy) match.
    A stock can appear multiple times if it triggers multiple strategies.
    """
    results = []

    for symbol, df in data.items():
        for strategy_fn in STRATEGIES:
            try:
                result = strategy_fn(df, symbol)
                if result:
                    log.info(f"  ✓ {symbol} — {result['strategy']}")
                    results.append(result)
            except Exception as e:
                log.error(f"  Error running {strategy_fn.__name__} on {symbol}: {e}")

    # Sort: strategies first, then alphabetical
    results.sort(key=lambda x: (x["strategy"], x["symbol"]))
    return results


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from screener.data_fetcher import fetch_all
    data = fetch_all(["TCS", "INFY", "RELIANCE", "HDFCBANK", "SBIN"])
    picks = screen_stocks(data)
    print(f"\n{'='*50}")
    print(f"Found {len(picks)} signals:")
    for p in picks:
        print(p)
