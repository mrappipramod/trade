"""
screener.py
Master screener — orchestrates data fetch, technicals, fundamentals,
and produces a final StockReport per symbol.

Usage:
    from screener.screener import run_screener
    reports = run_screener(cap_filter="midcap", max_stocks=50)
"""

import logging
import concurrent.futures
from dataclasses import dataclass, field
from typing import Optional

from screener.data_fetcher import fetch_stock_data
from screener.fundamental import FundamentalScore, fetch_fundamentals
from screener.technicals  import TechnicalSetup, compute_technical_setup
from screener.universe    import get_universe

log = logging.getLogger(__name__)


# ── Final report object ────────────────────────────────────────────────────────

@dataclass
class StockReport:
    symbol:       str
    cap_category: str    # largecap | midcap | smallcap

    tech:  Optional[TechnicalSetup]   = None
    fund:  Optional[FundamentalScore] = None

    # Composite
    composite_score:  int  = 0     # 0–100 (60% tech + 40% fund)
    overall_grade:    str  = ""    # A+ → D
    best_trade_type:  str  = ""    # INTRADAY | SWING | LONG_TERM | AVOID
    long_term_pick:   bool = False
    swing_pick:       bool = False
    intraday_pick:    bool = False
    summary:          str  = ""


def _build_report(symbol: str, cap_category: str) -> Optional[StockReport]:
    """Fetch data + run both analyses for one symbol."""
    try:
        # Fetch price data
        df = fetch_stock_data(symbol, period="1y")
        if df is None or len(df) < 50:
            return None

        # Technical analysis
        tech = compute_technical_setup(df, symbol)

        # Fundamental analysis
        fund = fetch_fundamentals(symbol)

        if tech is None:
            return None

        report = StockReport(symbol=symbol, cap_category=cap_category,
                             tech=tech, fund=fund)

        # ── Composite score ────────────────────────────────────────────────────
        tech_score = tech.technical_score if tech else 0
        fund_score = fund.total_score     if fund else 50  # neutral if unavailable

        report.composite_score = round(tech_score * 0.6 + fund_score * 0.4)

        # ── Grade ──────────────────────────────────────────────────────────────
        s = report.composite_score
        if   s >= 85: report.overall_grade = "A+"
        elif s >= 75: report.overall_grade = "A"
        elif s >= 65: report.overall_grade = "B+"
        elif s >= 55: report.overall_grade = "B"
        elif s >= 40: report.overall_grade = "C"
        else:         report.overall_grade = "D"

        # ── Trade type ─────────────────────────────────────────────────────────
        report.best_trade_type = tech.best_trade_type if tech else "AVOID"

        # Long-term: needs good fundamentals + uptrend
        lt_fund_ok   = fund and fund.total_score >= 60
        lt_tech_ok   = tech and tech.trend == "UPTREND" and tech.above_200ema
        report.long_term_pick = bool(lt_fund_ok and lt_tech_ok)

        # Swing: technical momentum signals, less strict on fundamentals
        sw_ok = (tech and
                 tech.technical_score >= 55 and
                 tech.best_trade_type in ("SWING", "LONG_TERM"))
        report.swing_pick = bool(sw_ok)

        # Intraday: high volume + clear momentum, RSI not extreme opposite
        intra_ok = (tech and
                    tech.volume_signal == "HIGH" and
                    tech.technical_score >= 50 and
                    tech.rsi_signal != ("OVERBOUGHT" if tech.trend == "UPTREND" else "OVERSOLD"))
        report.intraday_pick = bool(intra_ok)

        # ── Summary ────────────────────────────────────────────────────────────
        parts = []
        if tech:
            parts.append(f"{tech.trend} | RSI {tech.rsi} | Vol {tech.volume_signal}")
        if fund:
            parts.append(f"PE {fund.pe_ratio} | ROE {fund.roe}% | Grade {fund.grade}")
        if fund and fund.flags:
            parts.append(" | ".join(fund.flags[:2]))
        report.summary = "  •  ".join(parts)

        return report

    except Exception as e:
        log.error(f"[Screener] Error for {symbol}: {e}")
        return None


# ── Main screener ──────────────────────────────────────────────────────────────

def run_screener(
    cap_filter:    str = "all",      # largecap | midcap | smallcap | all
    max_stocks:    int = 100,        # max symbols to scan
    min_score:     int = 55,         # composite score threshold
    trade_filter:  str = "all",      # all | longterm | swing | intraday
    workers:       int = 4,          # parallel threads
) -> list:
    """
    Run the full techno-fundamental screener.

    Returns a list of StockReport objects sorted by composite score (desc).
    """
    from screener.universe import ALL_CAPS, LARGE_CAP, MID_CAP, SMALL_CAP

    # Build tagged symbol list: [(symbol, cap_category)]
    if cap_filter == "all":
        tagged = (
            [(s, "largecap")  for s in LARGE_CAP] +
            [(s, "midcap")    for s in MID_CAP]   +
            [(s, "smallcap")  for s in SMALL_CAP]
        )
    else:
        universe = get_universe(cap_filter)
        tagged = [(s, cap_filter) for s in universe]

    # Deduplicate keeping first occurrence
    seen = set(); deduped = []
    for sym, cap in tagged:
        if sym not in seen:
            seen.add(sym); deduped.append((sym, cap))

    tagged = deduped[:max_stocks]
    total  = len(tagged)
    log.info(f"Scanning {total} stocks (cap={cap_filter}, min_score={min_score})...")

    reports = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futures = {
            ex.submit(_build_report, sym, cap): (sym, cap)
            for sym, cap in tagged
        }
        for i, fut in enumerate(concurrent.futures.as_completed(futures), 1):
            sym, cap = futures[fut]
            try:
                report = fut.result()
                if report:
                    log.info(f"  [{i}/{total}] {sym:15s} score={report.composite_score:3d} "
                             f"grade={report.overall_grade} trade={report.best_trade_type}")
                    reports.append(report)
                else:
                    log.debug(f"  [{i}/{total}] {sym} — skipped (no data)")
            except Exception as e:
                log.error(f"  [{i}/{total}] {sym} — error: {e}")

    # Filter by score
    reports = [r for r in reports if r.composite_score >= min_score]

    # Filter by trade type
    if trade_filter == "longterm":
        reports = [r for r in reports if r.long_term_pick]
    elif trade_filter == "swing":
        reports = [r for r in reports if r.swing_pick]
    elif trade_filter == "intraday":
        reports = [r for r in reports if r.intraday_pick]

    # Sort by composite score
    reports.sort(key=lambda r: r.composite_score, reverse=True)

    log.info(f"Screener complete — {len(reports)} stocks passed filters.")
    return reports


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    reports = run_screener(cap_filter="largecap", max_stocks=10, min_score=50)
    print(f"\n{'='*70}")
    print(f"{'SYMBOL':<12} {'CAP':<10} {'SCORE':>5} {'GRADE':>5} {'BEST TRADE':<12} {'LONG?':>5} {'SWING?':>6}")
    print("-"*70)
    for r in reports:
        print(f"{r.symbol:<12} {r.cap_category:<10} {r.composite_score:>5} "
              f"{r.overall_grade:>5} {r.best_trade_type:<12} "
              f"{'✓' if r.long_term_pick else '✗':>5} {'✓' if r.swing_pick else '✗':>6}")
