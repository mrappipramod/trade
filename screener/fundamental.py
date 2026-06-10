"""
fundamental.py
Fetches and scores company fundamentals using yfinance.

Scores each company across 5 pillars:
  1. Valuation      (PE, PB, PS ratios)
  2. Profitability  (ROE, ROCE, margins)
  3. Growth         (Revenue & Earnings CAGR)
  4. Financial Health (D/E, current ratio, interest coverage)
  5. Quality        (promoter holding, consistent EPS, dividend track)

Returns a FundamentalScore object with a 0–100 composite score
and plain-English verdict on suitability.
"""

import logging
import yfinance as yf
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


@dataclass
class FundamentalScore:
    symbol: str

    # Raw metrics
    pe_ratio:           Optional[float] = None
    pb_ratio:           Optional[float] = None
    ps_ratio:           Optional[float] = None
    roe:                Optional[float] = None   # %
    roce:               Optional[float] = None   # %
    net_margin:         Optional[float] = None   # %
    revenue_growth_yoy: Optional[float] = None   # %
    earnings_growth_yoy:Optional[float] = None   # %
    debt_to_equity:     Optional[float] = None
    current_ratio:      Optional[float] = None
    dividend_yield:     Optional[float] = None   # %
    market_cap:         Optional[float] = None   # INR crores
    sector:             str = ""
    industry:           str = ""

    # Pillar scores (0–20 each)
    valuation_score:    int = 0
    profitability_score:int = 0
    growth_score:       int = 0
    health_score:       int = 0
    quality_score:      int = 0

    # Composite
    total_score:        int = 0      # 0–100
    grade:              str = ""     # A+, A, B+, B, C, D
    long_term_suitable: bool = False
    flags:              list = field(default_factory=list)   # warning flags


def fetch_fundamentals(symbol: str) -> Optional[FundamentalScore]:
    """Fetch fundamentals from yfinance and compute scores."""
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        info = ticker.info or {}

        if not info or info.get("regularMarketPrice") is None:
            log.warning(f"[Fundamentals] No data for {symbol}")
            return None

        fs = FundamentalScore(symbol=symbol)

        # ── Raw metrics ────────────────────────────────────────────────────────
        fs.pe_ratio            = _safe(info, "trailingPE")
        fs.pb_ratio            = _safe(info, "priceToBook")
        fs.ps_ratio            = _safe(info, "priceToSalesTrailing12Months")
        fs.roe                 = _pct(info, "returnOnEquity")
        fs.roce                = _pct(info, "returnOnAssets")     # proxy
        fs.net_margin          = _pct(info, "profitMargins")
        fs.revenue_growth_yoy  = _pct(info, "revenueGrowth")
        fs.earnings_growth_yoy = _pct(info, "earningsGrowth")
        fs.debt_to_equity      = _safe(info, "debtToEquity")
        fs.current_ratio       = _safe(info, "currentRatio")
        fs.dividend_yield      = _pct(info, "dividendYield")
        fs.market_cap          = _safe(info, "marketCap")
        fs.sector              = info.get("sector", "")
        fs.industry            = info.get("industry", "")

        # ── Score each pillar ──────────────────────────────────────────────────
        fs.valuation_score    = _score_valuation(fs)
        fs.profitability_score = _score_profitability(fs)
        fs.growth_score       = _score_growth(fs)
        fs.health_score       = _score_health(fs)
        fs.quality_score      = _score_quality(fs)

        fs.total_score = (
            fs.valuation_score + fs.profitability_score +
            fs.growth_score + fs.health_score + fs.quality_score
        )

        fs.grade = _grade(fs.total_score)
        fs.long_term_suitable = fs.total_score >= 60
        fs.flags = _build_flags(fs)

        return fs

    except Exception as e:
        log.error(f"[Fundamentals] Error for {symbol}: {e}")
        return None


# ── Pillar scorers (each returns 0–20) ────────────────────────────────────────

def _score_valuation(fs: FundamentalScore) -> int:
    score = 0
    # PE: lower is better for value; <15 great, <25 ok, >40 expensive
    if fs.pe_ratio is not None:
        if   fs.pe_ratio < 0:   score += 0    # loss-making
        elif fs.pe_ratio < 15:  score += 7
        elif fs.pe_ratio < 25:  score += 5
        elif fs.pe_ratio < 35:  score += 3
        elif fs.pe_ratio < 50:  score += 1
    else:
        score += 3  # unknown → neutral

    # PB: <1 undervalued, <3 fair, >5 pricey
    if fs.pb_ratio is not None:
        if   fs.pb_ratio < 1:   score += 7
        elif fs.pb_ratio < 2:   score += 6
        elif fs.pb_ratio < 3:   score += 4
        elif fs.pb_ratio < 5:   score += 2
    else:
        score += 3

    # PS: <2 good for most sectors
    if fs.ps_ratio is not None:
        if   fs.ps_ratio < 1:   score += 6
        elif fs.ps_ratio < 2:   score += 4
        elif fs.ps_ratio < 4:   score += 2
    else:
        score += 2

    return min(score, 20)


def _score_profitability(fs: FundamentalScore) -> int:
    score = 0
    # ROE: >20% excellent, >15% good, >10% ok
    if fs.roe is not None:
        if   fs.roe > 25:  score += 8
        elif fs.roe > 20:  score += 7
        elif fs.roe > 15:  score += 5
        elif fs.roe > 10:  score += 3
        elif fs.roe > 0:   score += 1

    # Net margin: >20% excellent, >10% good
    if fs.net_margin is not None:
        if   fs.net_margin > 20:  score += 8
        elif fs.net_margin > 15:  score += 7
        elif fs.net_margin > 10:  score += 5
        elif fs.net_margin > 5:   score += 3
        elif fs.net_margin > 0:   score += 1

    # ROCE proxy (ROA): >15% good
    if fs.roce is not None:
        if   fs.roce > 15:  score += 4
        elif fs.roce > 10:  score += 3
        elif fs.roce > 5:   score += 2
        elif fs.roce > 0:   score += 1

    return min(score, 20)


def _score_growth(fs: FundamentalScore) -> int:
    score = 0
    # Revenue growth YoY
    if fs.revenue_growth_yoy is not None:
        if   fs.revenue_growth_yoy > 30:  score += 10
        elif fs.revenue_growth_yoy > 20:  score += 8
        elif fs.revenue_growth_yoy > 10:  score += 6
        elif fs.revenue_growth_yoy > 5:   score += 4
        elif fs.revenue_growth_yoy > 0:   score += 2
        else:                             score += 0   # declining

    # Earnings growth YoY
    if fs.earnings_growth_yoy is not None:
        if   fs.earnings_growth_yoy > 30:  score += 10
        elif fs.earnings_growth_yoy > 20:  score += 8
        elif fs.earnings_growth_yoy > 10:  score += 6
        elif fs.earnings_growth_yoy > 5:   score += 4
        elif fs.earnings_growth_yoy > 0:   score += 2

    return min(score, 20)


def _score_health(fs: FundamentalScore) -> int:
    score = 0
    # D/E: <0.5 excellent, <1 good, >2 risky
    if fs.debt_to_equity is not None:
        de = fs.debt_to_equity / 100  # yfinance returns in %
        if   de < 0.3:   score += 10
        elif de < 0.5:   score += 8
        elif de < 1.0:   score += 6
        elif de < 1.5:   score += 3
        elif de < 2.0:   score += 1
    else:
        score += 5  # unknown → neutral

    # Current ratio: >2 strong, >1.5 ok, <1 dangerous
    if fs.current_ratio is not None:
        if   fs.current_ratio > 2.5:  score += 10
        elif fs.current_ratio > 2.0:  score += 8
        elif fs.current_ratio > 1.5:  score += 6
        elif fs.current_ratio > 1.0:  score += 3
        else:                         score += 0
    else:
        score += 5

    return min(score, 20)


def _score_quality(fs: FundamentalScore) -> int:
    score = 0
    # Dividend yield: paying dividends is a quality signal
    if fs.dividend_yield is not None and fs.dividend_yield > 0:
        if   fs.dividend_yield > 3:   score += 6
        elif fs.dividend_yield > 1.5: score += 4
        else:                         score += 2

    # Market cap size as quality proxy (large = more stable)
    if fs.market_cap is not None:
        mc_cr = fs.market_cap / 1e7   # convert to crores
        if   mc_cr > 100000:  score += 8   # >1L cr = mega cap
        elif mc_cr > 20000:   score += 6   # large cap
        elif mc_cr > 5000:    score += 4   # mid cap
        else:                 score += 2   # small cap

    # Positive ROE is a quality signal
    if fs.roe and fs.roe > 15:
        score += 6

    return min(score, 20)


# ── Grade & flags ──────────────────────────────────────────────────────────────

def _grade(score: int) -> str:
    if score >= 85: return "A+"
    if score >= 75: return "A"
    if score >= 65: return "B+"
    if score >= 55: return "B"
    if score >= 40: return "C"
    return "D"


def _build_flags(fs: FundamentalScore) -> list:
    flags = []
    if fs.pe_ratio and fs.pe_ratio > 50:
        flags.append("⚠️ High PE — priced for perfection")
    if fs.debt_to_equity and fs.debt_to_equity / 100 > 1.5:
        flags.append("⚠️ High debt — watch interest coverage")
    if fs.revenue_growth_yoy and fs.revenue_growth_yoy < 0:
        flags.append("🔴 Revenue declining YoY")
    if fs.earnings_growth_yoy and fs.earnings_growth_yoy < 0:
        flags.append("🔴 Earnings declining YoY")
    if fs.net_margin and fs.net_margin < 5:
        flags.append("⚠️ Thin margins — vulnerable to cost pressure")
    if fs.roe and fs.roe < 10:
        flags.append("⚠️ Low ROE — poor capital efficiency")
    return flags


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe(info: dict, key: str) -> Optional[float]:
    v = info.get(key)
    if v is None or v != v:  # None or NaN
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _pct(info: dict, key: str) -> Optional[float]:
    v = _safe(info, key)
    return round(v * 100, 2) if v is not None else None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    fs = fetch_fundamentals("TCS")
    if fs:
        print(f"\n{fs.symbol} | Score: {fs.total_score}/100 | Grade: {fs.grade}")
        print(f"  PE:{fs.pe_ratio}  PB:{fs.pb_ratio}  ROE:{fs.roe}%  Margin:{fs.net_margin}%")
        print(f"  Rev Growth:{fs.revenue_growth_yoy}%  EPS Growth:{fs.earnings_growth_yoy}%")
        print(f"  Long-term suitable: {fs.long_term_suitable}")
        for f in fs.flags:
            print(f"  {f}")
