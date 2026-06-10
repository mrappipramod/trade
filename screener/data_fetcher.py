import yfinance as yf
import pandas as pd

NIFTY_50 = ["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", ...]

def fetch_stock_data(symbol: str, period="3mo") -> pd.DataFrame:
    ticker = yf.Ticker(f"{symbol}.NS")
    df = ticker.history(period=period)
    df["symbol"] = symbol
    return df

def fetch_all(symbols=NIFTY_50) -> dict:
    return {s: fetch_stock_data(s) for s in symbols}
