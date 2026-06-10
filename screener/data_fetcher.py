"""
data_fetcher.py
Fetches OHLCV data for Indian stocks (NSE) using yfinance.

Usage:
    from screener.data_fetcher import fetch_all, NIFTY_50
    data = fetch_all()          # returns {symbol: pd.DataFrame}
    data = fetch_all(["TCS", "INFY"])  # fetch a subset
"""

import logging
import yfinance as yf
import pandas as pd
from typing import Optional

log = logging.getLogger(__name__)

# ── Stock universes ────────────────────────────────────────────────────────────

NIFTY_50 = [
    "ADANIENT", "ADANIPORTS", "APOLLOHOSP", "ASIANPAINT", "AXISBANK",
    "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BPCL", "BHARTIARTL",
    "BRITANNIA", "CIPLA", "COALINDIA", "DIVISLAB", "DRREDDY",
    "EICHERMOT", "GRASIM", "HCLTECH", "HDFCBANK", "HDFCLIFE",
    "HEROMOTOCO", "HINDALCO", "HINDUNILVR", "ICICIBANK", "ITC",
    "INDUSINDBK", "INFY", "JSWSTEEL", "KOTAKBANK", "LT",
    "LTIM", "M&M", "MARUTI", "NTPC", "NESTLEIND",
    "ONGC", "POWERGRID", "RELIANCE", "SBILIFE", "SHRIRAMFIN",
    "SBIN", "SUNPHARMA", "TCS", "TATACONSUM", "TATAMOTORS",
    "TATASTEEL", "TECHM", "TITAN", "ULTRACEMCO", "WIPRO",
]

NIFTY_NEXT_50 = [
    "ABB", "ADANIGREEN", "ADANITRANS", "AMBUJACEM", "AUROPHARMA",
    "BANDHANBNK", "BANKBARODA", "BERGEPAINT", "BEL", "BOSCHLTD",
    "CHOLAFIN", "COLPAL", "DABUR", "DLF", "GAIL",
    "GODREJCP", "GODREJPROP", "HAL", "HAVELLS", "ICICIGI",
    "ICICIPRULI", "INDHOTEL", "IOC", "IRCTC", "JINDALSTEL",
    "JUBLFOOD", "LICI", "LUPIN", "MCDOWELL-N", "MPHASIS",
    "NAUKRI", "NHPC", "NMDC", "OFSS", "PIDILITIND",
    "PIIND", "PNB", "RECLTD", "SAIL", "SRF",
    "SIEMENS", "TATACOMM", "TATAPOWER", "TORNTPHARM", "TRENT",
    "UNIONBANK", "UPL", "VBL", "VEDL", "ZYDUSLIFE",
]

# Combined list — use this for a broad scan
ALL_STOCKS = list(dict.fromkeys(NIFTY_50 + NIFTY_NEXT_50))  # deduplicated


# ── Fetcher ────────────────────────────────────────────────────────────────────

def fetch_stock_data(symbol: str, period: str = "6mo") -> Optional[pd.DataFrame]:
    """
    Download historical OHLCV data for a single NSE stock.

    Args:
        symbol: NSE ticker without suffix, e.g. "TCS"
        period: yfinance period string — "1mo", "3mo", "6mo", "1y", "2y"

    Returns:
        DataFrame with columns [Open, High, Low, Close, Volume, symbol]
        or None if the download fails / returns empty.
    """
    ticker_symbol = f"{symbol}.NS"
    try:
        ticker = yf.Ticker(ticker_symbol)
        df = ticker.history(period=period, auto_adjust=True)

        if df.empty:
            log.warning(f"No data returned for {symbol}")
            return None

        df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
        df.dropna(inplace=True)
        df["symbol"] = symbol
        return df

    except Exception as e:
        log.error(f"Error fetching {symbol}: {e}")
        return None


def fetch_all(
    symbols: Optional[list] = None,
    period: str = "6mo",
) -> dict:
    """
    Fetch data for a list of symbols (defaults to NIFTY_50).

    Returns:
        dict mapping symbol -> DataFrame (failed symbols are omitted)
    """
    if symbols is None:
        symbols = NIFTY_50

    results = {}
    total = len(symbols)

    for i, symbol in enumerate(symbols, 1):
        log.info(f"  [{i}/{total}] Fetching {symbol}...")
        df = fetch_stock_data(symbol, period=period)
        if df is not None:
            results[symbol] = df

    log.info(f"Successfully fetched {len(results)}/{total} stocks.")
    return results


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    data = fetch_all(["TCS", "INFY", "RELIANCE"])
    for sym, df in data.items():
        print(f"\n{sym}: {len(df)} rows | Latest close: ₹{df['Close'].iloc[-1]:.2f}")
