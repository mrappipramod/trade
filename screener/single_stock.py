"""
single_stock.py
Full techno-fundamental analysis for a single stock.
Returns a detailed StockReport — same format as the screener.
"""

import logging
from screener.data_fetcher import fetch_stock_data
from screener.fundamental  import fetch_fundamentals
from screener.technicals   import compute_technical_setup
from screener.screener     import StockReport

log = logging.getLogger(__name__)


def analyse_single(symbol: str) -> StockReport | None:
    """
    Run complete techno-fundamental analysis on one stock.
    symbol: NSE ticker without .NS suffix (e.g. "TCS", "RELIANCE")
    """
    symbol = symbol.upper().strip()
    log.info(f"Analysing {symbol}...")

    df = fetch_stock_data(symbol, period="1y")
    if df is None or len(df) < 50:
        log.error(f"Insufficient price data for {symbol}")
        return None

    tech = compute_technical_setup(df, symbol)
    fund = fetch_fundamentals(symbol)

    if tech is None:
        log.error(f"Technical analysis failed for {symbol}")
        return None

    # Determine cap category from market cap
    cap = "unknown"
    if fund and fund.market_cap:
        mc_cr = fund.market_cap / 1e7
        if   mc_cr > 20000: cap = "largecap"
        elif mc_cr > 5000:  cap = "midcap"
        else:               cap = "smallcap"

    report = StockReport(symbol=symbol, cap_category=cap, tech=tech, fund=fund)

    tech_score = tech.technical_score
    fund_score = fund.total_score if fund else 50
    report.composite_score = round(tech_score * 0.6 + fund_score * 0.4)

    s = report.composite_score
    if   s >= 85: report.overall_grade = "A+"
    elif s >= 75: report.overall_grade = "A"
    elif s >= 65: report.overall_grade = "B+"
    elif s >= 55: report.overall_grade = "B"
    elif s >= 40: report.overall_grade = "C"
    else:         report.overall_grade = "D"

    report.best_trade_type  = tech.best_trade_type
    report.long_term_pick   = bool(fund and fund.total_score >= 60 and tech.trend == "UPTREND" and tech.above_200ema)
    report.swing_pick       = bool(tech.technical_score >= 55 and tech.best_trade_type in ("SWING","LONG_TERM"))
    report.intraday_pick    = bool(tech.volume_signal == "HIGH" and tech.technical_score >= 50)

    parts = []
    if tech: parts.append(f"{tech.trend} | RSI {tech.rsi} | Vol {tech.volume_signal}")
    if fund: parts.append(f"PE {fund.pe_ratio} | ROE {fund.roe}% | Grade {fund.grade}")
    report.summary = "  •  ".join(parts)

    return report
