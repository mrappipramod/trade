from ta.momentum import RSIIndicator

def screen_stocks(data: dict) -> list:
    selected = []
    for symbol, df in data.items():
        df["rsi"] = RSIIndicator(df["Close"]).rsi()
        latest_rsi = df["rsi"].iloc[-1]
        avg_vol = df["Volume"].mean()
        latest_vol = df["Volume"].iloc[-1]

        # Example: oversold + volume spike
        if latest_rsi < 35 and latest_vol > 1.5 * avg_vol:
            selected.append({
                "symbol": symbol,
                "rsi": round(latest_rsi, 2),
                "close": round(df["Close"].iloc[-1], 2)
            })
    return selected
