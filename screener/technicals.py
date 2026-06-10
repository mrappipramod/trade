"""
technicals.py
Computes all technical indicators and generates trade setups.

For each stock it produces a TechnicalSetup with:
  - Trade type verdict: INTRADAY | SWING | LONG_TERM | AVOID
  - Entry price, Target 1, Target 2, Stop Loss
  - Risk-Reward ratio
  - Trend, momentum, and volume signals
"""

import logging
import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


# ── Data classes ───────────────────────────────────────────────────────────────

@dataclass
class TradeSetup:
    """Actionable price levels for a specific trade type."""
    trade_type:   str    # INTRADAY | SWING | LONG_TERM
    entry:        float
    target1:      float
    target2:      float
    stop_loss:    float
    risk_reward:  float  # (T1 - Entry) / (Entry - SL)
    rationale:    str


@dataclass
class TechnicalSetup:
    symbol: str
    close:  float
    atr:    float    # Average True Range (daily volatility)

    # Trend
    trend:           str = ""   # UPTREND | DOWNTREND | SIDEWAYS
    above_50ema:     bool = False
    above_200ema:    bool = False
    ema_alignment:   bool = False   # EMA9 > EMA21 > EMA50

    # Momentum
    rsi:             Optional[float] = None
    rsi_signal:      str = ""   # OVERSOLD | NEUTRAL | OVERBOUGHT
    macd_cross:      str = ""   # BULLISH | BEARISH | NONE
    macd_above_zero: bool = False

    # Volume
    volume_signal:   str = ""   # HIGH | NORMAL | LOW
    vol_ratio:       float = 0  # today / 20d avg

    # Support / Resistance
    support:         float = 0
    resistance:      float = 0

    # Candlestick pattern
    candle_pattern:  str = ""

    # Trade setups
    intraday:        Optional[TradeSetup] = None
    swing:           Optional[TradeSetup] = None
    long_term:       Optional[TradeSetup] = None

    # Overall verdict
    best_trade_type: str = ""   # INTRADAY | SWING | LONG_TERM | AVOID
    technical_score: int = 0    # 0–100
    signals:         list = field(default_factory=list)


# ── Indicator functions ────────────────────────────────────────────────────────

def _ema(s: pd.Series, n: int) -> pd.Series:
    return s.ewm(span=n, adjust=False).mean()

def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()

def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    d = s.diff()
    g = d.clip(lower=0).ewm(com=n-1, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(com=n-1, adjust=False).mean()
    return 100 - 100 / (1 + g / l.replace(0, np.nan))

def _macd(s: pd.Series):
    fast = _ema(s, 12); slow = _ema(s, 26)
    line = fast - slow; signal = _ema(line, 9)
    return line, signal, line - signal

def _atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hl = df["High"] - df["Low"]
    hc = (df["High"] - df["Close"].shift()).abs()
    lc = (df["Low"]  - df["Close"].shift()).abs()
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    return tr.ewm(com=n-1, adjust=False).mean()

def _bollinger(s: pd.Series, n=20, std=2):
    mid = _sma(s, n); dev = s.rolling(n).std()
    return mid + std*dev, mid, mid - std*dev

def _support_resistance(df: pd.DataFrame, lookback: int = 50):
    """Simple swing high / swing low over lookback bars."""
    recent = df.tail(lookback)
    support    = float(recent["Low"].min())
    resistance = float(recent["High"].max())
    # refine: use most-tested level in middle range
    mid = (support + resistance) / 2
    lower_half = recent[recent["Close"] < mid]
    upper_half = recent[recent["Close"] > mid]
    if not lower_half.empty:
        support = float(lower_half["Low"].quantile(0.1))
    if not upper_half.empty:
        resistance = float(upper_half["High"].quantile(0.9))
    return round(support, 2), round(resistance, 2)

def _candle_pattern(df: pd.DataFrame) -> str:
    """Detect last-candle pattern."""
    c = df.iloc[-1]; p = df.iloc[-2]
    body = abs(c["Close"] - c["Open"])
    total_range = c["High"] - c["Low"]
    if total_range == 0:
        return ""

    upper_wick = c["High"] - max(c["Open"], c["Close"])
    lower_wick = min(c["Open"], c["Close"]) - c["Low"]
    body_pct = body / total_range

    # Doji
    if body_pct < 0.1:
        return "Doji (indecision)"

    # Hammer (bullish reversal)
    if lower_wick > 2 * body and upper_wick < body * 0.3 and c["Close"] > c["Open"]:
        return "Hammer (bullish reversal)"

    # Shooting star (bearish reversal)
    if upper_wick > 2 * body and lower_wick < body * 0.3 and c["Close"] < c["Open"]:
        return "Shooting Star (bearish reversal)"

    # Bullish engulfing
    if (c["Close"] > c["Open"] and p["Close"] < p["Open"]
            and c["Open"] < p["Close"] and c["Close"] > p["Open"]):
        return "Bullish Engulfing"

    # Bearish engulfing
    if (c["Close"] < c["Open"] and p["Close"] > p["Open"]
            and c["Open"] > p["Close"] and c["Close"] < p["Open"]):
        return "Bearish Engulfing"

    # Marubozu (strong directional)
    if body_pct > 0.85:
        return "Bullish Marubozu" if c["Close"] > c["Open"] else "Bearish Marubozu"

    return ""


# ── Price level calculator ─────────────────────────────────────────────────────

def _intraday_setup(close: float, atr: float, support: float, resistance: float, bullish: bool) -> TradeSetup:
    """
    Intraday: tight levels using 0.5× ATR increments.
    Entry near current price; SL below support or 0.5×ATR.
    """
    if bullish:
        entry    = round(close, 2)
        sl       = round(max(close - 0.5 * atr, support), 2)
        t1       = round(close + 0.75 * atr, 2)
        t2       = round(close + 1.5  * atr, 2)
    else:
        entry    = round(close, 2)
        sl       = round(min(close + 0.5 * atr, resistance), 2)
        t1       = round(close - 0.75 * atr, 2)
        t2       = round(close - 1.5  * atr, 2)

    risk   = abs(entry - sl)
    reward = abs(t1 - entry)
    rr     = round(reward / risk, 2) if risk > 0 else 0
    direction = "LONG" if bullish else "SHORT"
    return TradeSetup(
        trade_type="INTRADAY", entry=entry, target1=t1, target2=t2,
        stop_loss=sl, risk_reward=rr,
        rationale=f"{direction} intraday — 0.5×ATR SL, exit same day"
    )


def _swing_setup(close: float, atr: float, support: float, resistance: float, bullish: bool) -> TradeSetup:
    """
    Swing: 3–10 day hold. 1.5–2×ATR targets, 1×ATR SL.
    """
    if bullish:
        entry = round(close, 2)
        sl    = round(max(close - 1.0 * atr, support * 0.99), 2)
        t1    = round(close + 1.5 * atr, 2)
        t2    = round(min(close + 3.0 * atr, resistance * 0.99), 2)
    else:
        entry = round(close, 2)
        sl    = round(min(close + 1.0 * atr, resistance * 1.01), 2)
        t1    = round(close - 1.5 * atr, 2)
        t2    = round(max(close - 3.0 * atr, support * 1.01), 2)

    risk   = abs(entry - sl)
    reward = abs(t1 - entry)
    rr     = round(reward / risk, 2) if risk > 0 else 0
    direction = "LONG" if bullish else "SHORT"
    return TradeSetup(
        trade_type="SWING", entry=entry, target1=t1, target2=t2,
        stop_loss=sl, risk_reward=rr,
        rationale=f"{direction} swing — 1×ATR SL, hold 3–10 days"
    )


def _longterm_setup(close: float, atr: float, support: float, resistance: float) -> TradeSetup:
    """
    Long term: accumulate near support; 15–30% targets, wider SL.
    """
    entry = round(close, 2)
    sl    = round(support * 0.95, 2)
    t1    = round(close * 1.15, 2)
    t2    = round(close * 1.30, 2)
    risk   = abs(entry - sl)
    reward = abs(t1 - entry)
    rr     = round(reward / risk, 2) if risk > 0 else 0
    return TradeSetup(
        trade_type="LONG_TERM", entry=entry, target1=t1, target2=t2,
        stop_loss=sl, risk_reward=rr,
        rationale="Accumulate on dips; hold 6–18 months"
    )


# ── Master builder ─────────────────────────────────────────────────────────────

def compute_technical_setup(df: pd.DataFrame, symbol: str) -> Optional[TechnicalSetup]:
    """Run all technicals on a DataFrame and return a TechnicalSetup."""
    if len(df) < 50:
        log.warning(f"[Tech] Not enough data for {symbol} ({len(df)} bars)")
        return None

    try:
        df = df.copy()

        # ── Indicators ────────────────────────────────────────────────────────
        df["ema9"]  = _ema(df["Close"], 9)
        df["ema21"] = _ema(df["Close"], 21)
        df["ema50"] = _ema(df["Close"], 50)
        df["ema200"]= _ema(df["Close"], 200) if len(df) >= 200 else _sma(df["Close"], len(df))
        df["rsi"]   = _rsi(df["Close"])
        df["macd"], df["macd_sig"], df["macd_hist"] = _macd(df["Close"])
        df["atr"]   = _atr(df)
        df["vol_ma"]= _sma(df["Volume"], 20)
        bb_up, bb_mid, bb_low = _bollinger(df["Close"])
        df["bb_up"] = bb_up; df["bb_low"] = bb_low

        r = df.iloc[-1]   # latest row
        p = df.iloc[-2]   # previous row
        close = float(r["Close"])
        atr   = float(r["atr"])

        ts = TechnicalSetup(symbol=symbol, close=round(close, 2), atr=round(atr, 2))

        # ── Trend ─────────────────────────────────────────────────────────────
        ts.above_50ema  = close > float(r["ema50"])
        ts.above_200ema = close > float(r["ema200"])
        ts.ema_alignment = (float(r["ema9"]) > float(r["ema21"]) > float(r["ema50"]))

        if ts.above_50ema and ts.above_200ema:
            ts.trend = "UPTREND"
        elif not ts.above_50ema and not ts.above_200ema:
            ts.trend = "DOWNTREND"
        else:
            ts.trend = "SIDEWAYS"

        # ── RSI ───────────────────────────────────────────────────────────────
        ts.rsi = round(float(r["rsi"]), 2)
        if   ts.rsi < 35:   ts.rsi_signal = "OVERSOLD"
        elif ts.rsi > 65:   ts.rsi_signal = "OVERBOUGHT"
        else:               ts.rsi_signal = "NEUTRAL"

        # ── MACD ──────────────────────────────────────────────────────────────
        macd_cross_up   = p["macd"] <= p["macd_sig"] and r["macd"] > r["macd_sig"]
        macd_cross_down = p["macd"] >= p["macd_sig"] and r["macd"] < r["macd_sig"]
        if   macd_cross_up:   ts.macd_cross = "BULLISH"
        elif macd_cross_down: ts.macd_cross = "BEARISH"
        else:                 ts.macd_cross = "NONE"
        ts.macd_above_zero = float(r["macd"]) > 0

        # ── Volume ────────────────────────────────────────────────────────────
        vol_ratio = float(r["Volume"]) / float(r["vol_ma"]) if float(r["vol_ma"]) > 0 else 1
        ts.vol_ratio = round(vol_ratio, 2)
        if   vol_ratio > 2:   ts.volume_signal = "HIGH"
        elif vol_ratio > 0.7: ts.volume_signal = "NORMAL"
        else:                 ts.volume_signal = "LOW"

        # ── Support / Resistance ───────────────────────────────────────────────
        ts.support, ts.resistance = _support_resistance(df)

        # ── Candle pattern ─────────────────────────────────────────────────────
        ts.candle_pattern = _candle_pattern(df)

        # ── Technical score (0–100) ────────────────────────────────────────────
        score = 0
        signals = []

        if ts.trend == "UPTREND":         score += 25; signals.append("✅ Uptrend confirmed")
        elif ts.trend == "SIDEWAYS":      score += 10; signals.append("➡️ Sideways trend")
        else:                             signals.append("🔴 Downtrend — caution")

        if ts.ema_alignment:              score += 15; signals.append("✅ EMA aligned (9>21>50)")
        if ts.rsi_signal == "OVERSOLD":   score += 15; signals.append("✅ RSI oversold — potential bounce")
        elif ts.rsi_signal == "NEUTRAL":  score += 10
        else:                             signals.append("⚠️ RSI overbought — risk of pullback")

        if ts.macd_cross == "BULLISH":    score += 15; signals.append("✅ MACD bullish crossover")
        elif ts.macd_above_zero:          score += 8
        elif ts.macd_cross == "BEARISH":  signals.append("🔴 MACD bearish crossover")

        if ts.volume_signal == "HIGH":    score += 15; signals.append("✅ Volume spike — strong conviction")
        elif ts.volume_signal == "NORMAL":score += 8
        else:                             signals.append("⚠️ Low volume — weak move")

        if ts.above_200ema:               score += 10; signals.append("✅ Above 200 EMA — long-term bullish")
        if ts.candle_pattern:             signals.append(f"🕯 {ts.candle_pattern}")
        if close <= ts.support * 1.02:    signals.append("📌 Near support — low-risk entry zone")
        if close >= ts.resistance * 0.98: signals.append("📌 Near resistance — watch for breakout/rejection")

        ts.technical_score = min(score, 100)
        ts.signals = signals

        # ── Determine bullish/bearish bias ─────────────────────────────────────
        bullish = ts.technical_score >= 50

        # ── Build trade setups ─────────────────────────────────────────────────
        ts.intraday  = _intraday_setup(close, atr, ts.support, ts.resistance, bullish)
        ts.swing     = _swing_setup(close, atr, ts.support, ts.resistance, bullish)
        ts.long_term = _longterm_setup(close, atr, ts.support, ts.resistance)

        # ── Best trade type recommendation ─────────────────────────────────────
        if ts.technical_score < 35:
            ts.best_trade_type = "AVOID"
        elif ts.volume_signal == "HIGH" and abs(ts.rsi - 50) > 10:
            ts.best_trade_type = "INTRADAY"
        elif ts.macd_cross == "BULLISH" or ts.rsi_signal == "OVERSOLD":
            ts.best_trade_type = "SWING"
        elif ts.trend == "UPTREND" and ts.above_200ema:
            ts.best_trade_type = "LONG_TERM"
        else:
            ts.best_trade_type = "SWING"

        return ts

    except Exception as e:
        log.error(f"[Tech] Error for {symbol}: {e}")
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from screener.data_fetcher import fetch_stock_data
    df = fetch_stock_data("TCS", period="1y")
    if df is not None:
        ts = compute_technical_setup(df, "TCS")
        if ts:
            print(f"\n{ts.symbol} | ₹{ts.close} | {ts.trend} | Score: {ts.technical_score}/100")
            print(f"  RSI: {ts.rsi} ({ts.rsi_signal}) | MACD: {ts.macd_cross} | Vol: {ts.volume_signal}")
            print(f"  Best Trade: {ts.best_trade_type}")
            print(f"  Swing — Entry: {ts.swing.entry}  T1: {ts.swing.target1}  T2: {ts.swing.target2}  SL: {ts.swing.stop_loss}  RR: {ts.swing.risk_reward}")
            for s in ts.signals:
                print(f"  {s}")
