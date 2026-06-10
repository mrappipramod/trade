"""
report_builder.py
Formats StockReport objects into rich messages for Telegram, Email, and console.
"""

from datetime import date
from screener.screener import StockReport


def _cap_badge(cap: str) -> str:
    return {"largecap": "🔵 Large", "midcap": "🟡 Mid", "smallcap": "🟢 Small"}.get(cap, cap)

def _trade_badge(t: str) -> str:
    return {"INTRADAY": "⚡ Intraday", "SWING": "🔄 Swing",
            "LONG_TERM": "📈 Long Term", "AVOID": "🚫 Avoid"}.get(t, t)

def _grade_emoji(g: str) -> str:
    return {"A+": "🏆", "A": "⭐", "B+": "✅", "B": "👍", "C": "⚠️", "D": "🔴"}.get(g, "")


# ── Telegram markdown ──────────────────────────────────────────────────────────

def format_telegram(reports: list, cap_filter: str = "all") -> list:
    """Returns a list of Telegram markdown message strings (split for 4096 char limit)."""
    today = date.today().strftime("%d %b %Y")
    cap_label = cap_filter.upper() if cap_filter != "all" else "ALL CAPS"

    header = (
        f"📊 *Trade Screener — {today}*\n"
        f"_{cap_label} | {len(reports)} stock(s) selected_\n"
    )

    sections = [header]

    for r in reports:
        t = r.tech
        f = r.fund
        ts = t.swing if t else None   # default to swing levels

        block = f"\n{'─'*30}\n"
        block += f"*{r.symbol}*  {_cap_badge(r.cap_category)}  {_grade_emoji(r.overall_grade)} Grade {r.overall_grade}  Score {r.composite_score}/100\n"
        block += f"_{_trade_badge(r.best_trade_type)}_"

        trades = []
        if r.long_term_pick:  trades.append("📈 Long Term")
        if r.swing_pick:      trades.append("🔄 Swing")
        if r.intraday_pick:   trades.append("⚡ Intraday")
        if trades:
            block += f"  |  Suitable for: {', '.join(trades)}"
        block += "\n"

        # Price levels
        if t:
            block += f"\n💰 *CMP:* ₹{t.close}  |  ATR: ₹{t.atr}\n"
            block += f"📍 Support: ₹{t.support}  |  Resistance: ₹{t.resistance}\n"

        # Trade setups
        if r.best_trade_type == "INTRADAY" and t and t.intraday:
            s = t.intraday
            block += f"\n⚡ *Intraday Setup*\n"
            block += f"  Entry: ₹{s.entry}  |  T1: ₹{s.target1}  |  T2: ₹{s.target2}\n"
            block += f"  SL: ₹{s.stop_loss}  |  R:R = 1:{s.risk_reward}\n"

        if r.swing_pick and t and t.swing:
            s = t.swing
            block += f"\n🔄 *Swing Setup* (3–10 days)\n"
            block += f"  Entry: ₹{s.entry}  |  T1: ₹{s.target1}  |  T2: ₹{s.target2}\n"
            block += f"  SL: ₹{s.stop_loss}  |  R:R = 1:{s.risk_reward}\n"

        if r.long_term_pick and t and t.long_term:
            s = t.long_term
            block += f"\n📈 *Long Term Setup* (6–18 months)\n"
            block += f"  Entry: ₹{s.entry}  |  T1: ₹{s.target1} (+15%)  |  T2: ₹{s.target2} (+30%)\n"
            block += f"  SL: ₹{s.stop_loss}  |  R:R = 1:{s.risk_reward}\n"

        # Technical signals
        if t and t.signals:
            block += f"\n📡 *Signals:*\n"
            for sig in t.signals[:5]:
                block += f"  {sig}\n"

        # Fundamental highlights
        if f:
            block += f"\n🏢 *Fundamentals:* PE {f.pe_ratio} | ROE {f.roe}% | Margin {f.net_margin}%\n"
            block += f"  Rev Growth {f.revenue_growth_yoy}% | EPS Growth {f.earnings_growth_yoy}%\n"
            if f.flags:
                for flag in f.flags[:2]:
                    block += f"  {flag}\n"

        sections.append(block)

    # Chunk into messages under 4000 chars
    messages = []
    current = ""
    for section in sections:
        if len(current) + len(section) > 4000:
            if current:
                messages.append(current)
            current = section
        else:
            current += section
    if current:
        messages.append(current)

    messages.append("\n_Data: NSE via yfinance • Not financial advice_")
    return messages


# ── HTML email ─────────────────────────────────────────────────────────────────

def format_html_email(reports: list, cap_filter: str = "all") -> str:
    today = date.today().strftime("%d %b %Y")
    cap_label = cap_filter.upper() if cap_filter != "all" else "All Caps"

    rows = ""
    for r in reports:
        t = r.tech
        f = r.fund

        # Trade badges
        badges = ""
        if r.long_term_pick:  badges += '<span style="background:#166534;color:#dcfce7;padding:2px 6px;border-radius:4px;font-size:11px;margin-right:4px;">📈 LT</span>'
        if r.swing_pick:      badges += '<span style="background:#854d0e;color:#fef9c3;padding:2px 6px;border-radius:4px;font-size:11px;margin-right:4px;">🔄 Swing</span>'
        if r.intraday_pick:   badges += '<span style="background:#1e3a5f;color:#bfdbfe;padding:2px 6px;border-radius:4px;font-size:11px;">⚡ Intraday</span>'

        # Grade colour
        grade_color = {"A+":"#16a34a","A":"#22c55e","B+":"#84cc16","B":"#eab308","C":"#f97316","D":"#ef4444"}.get(r.overall_grade, "#888")

        swing_row = ""
        if r.swing_pick and t and t.swing:
            s = t.swing
            swing_row = f"""<tr style="background:#1e293b;">
              <td colspan="2" style="padding:6px 12px;font-size:12px;color:#94a3b8;">🔄 Swing</td>
              <td style="padding:6px 12px;font-size:12px;">₹{s.entry}</td>
              <td style="padding:6px 12px;font-size:12px;color:#4ade80;">₹{s.target1}</td>
              <td style="padding:6px 12px;font-size:12px;color:#4ade80;">₹{s.target2}</td>
              <td style="padding:6px 12px;font-size:12px;color:#f87171;">₹{s.stop_loss}</td>
              <td style="padding:6px 12px;font-size:12px;">1:{s.risk_reward}</td>
            </tr>"""

        lt_row = ""
        if r.long_term_pick and t and t.long_term:
            s = t.long_term
            lt_row = f"""<tr style="background:#172554;">
              <td colspan="2" style="padding:6px 12px;font-size:12px;color:#94a3b8;">📈 Long Term</td>
              <td style="padding:6px 12px;font-size:12px;">₹{s.entry}</td>
              <td style="padding:6px 12px;font-size:12px;color:#4ade80;">₹{s.target1}</td>
              <td style="padding:6px 12px;font-size:12px;color:#4ade80;">₹{s.target2}</td>
              <td style="padding:6px 12px;font-size:12px;color:#f87171;">₹{s.stop_loss}</td>
              <td style="padding:6px 12px;font-size:12px;">1:{s.risk_reward}</td>
            </tr>"""

        intra_row = ""
        if r.intraday_pick and t and t.intraday:
            s = t.intraday
            intra_row = f"""<tr style="background:#0c1a2e;">
              <td colspan="2" style="padding:6px 12px;font-size:12px;color:#94a3b8;">⚡ Intraday</td>
              <td style="padding:6px 12px;font-size:12px;">₹{s.entry}</td>
              <td style="padding:6px 12px;font-size:12px;color:#4ade80;">₹{s.target1}</td>
              <td style="padding:6px 12px;font-size:12px;color:#4ade80;">₹{s.target2}</td>
              <td style="padding:6px 12px;font-size:12px;color:#f87171;">₹{s.stop_loss}</td>
              <td style="padding:6px 12px;font-size:12px;">1:{s.risk_reward}</td>
            </tr>"""

        rows += f"""
        <tr style="border-top:2px solid #334155;">
          <td style="padding:10px 12px;font-weight:bold;font-size:15px;">{r.symbol}</td>
          <td style="padding:10px 12px;font-size:12px;color:#94a3b8;">{_cap_badge(r.cap_category)}</td>
          <td colspan="4" style="padding:10px 12px;">{badges}</td>
          <td style="padding:10px 12px;font-weight:bold;color:{grade_color};">{r.overall_grade} ({r.composite_score})</td>
        </tr>
        {swing_row}{lt_row}{intra_row}
        """
        if t:
            fund_txt = f"PE {f.pe_ratio} | ROE {f.roe}% | Rev↑{f.revenue_growth_yoy}%" if f else "Fundamentals N/A"
            rows += f"""<tr style="background:#0f172a;">
              <td colspan="7" style="padding:6px 12px;font-size:11px;color:#64748b;">
                {t.trend} | RSI {t.rsi} | Vol {t.volume_signal} | Support ₹{t.support} | Resistance ₹{t.resistance}
                &nbsp;&nbsp;|&nbsp;&nbsp; {fund_txt}
              </td>
            </tr>"""

    return f"""<!DOCTYPE html><html>
<body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px;margin:0;">
  <div style="max-width:900px;margin:auto;">
    <div style="background:#1e293b;border-radius:8px 8px 0 0;padding:20px 24px;">
      <h2 style="margin:0;color:#fff;">📊 Trade Screener — {today}</h2>
      <p style="margin:6px 0 0;color:#94a3b8;">{cap_label} scan • {len(reports)} stock(s) selected</p>
    </div>
    <table style="width:100%;border-collapse:collapse;background:#1e293b;font-size:13px;">
      <thead>
        <tr style="background:#0f172a;color:#64748b;font-size:11px;text-transform:uppercase;">
          <th style="padding:8px 12px;text-align:left;">Symbol</th>
          <th style="padding:8px 12px;text-align:left;">Cap</th>
          <th style="padding:8px 12px;text-align:left;">Type</th>
          <th style="padding:8px 12px;text-align:left;">Entry</th>
          <th style="padding:8px 12px;text-align:left;">T1</th>
          <th style="padding:8px 12px;text-align:left;">T2</th>
          <th style="padding:8px 12px;text-align:left;">SL</th>
          <th style="padding:8px 12px;text-align:left;">R:R</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
    <div style="background:#0f172a;padding:12px 24px;font-size:11px;color:#475569;border-radius:0 0 8px 8px;">
      Data via NSE • Generated by Trade Screener • Not financial advice
    </div>
  </div>
</body></html>"""


# ── Console / plain text ───────────────────────────────────────────────────────

def format_console(reports: list) -> str:
    lines = [f"\n{'='*75}",
             f"  TRADE SCREENER — {date.today().strftime('%d %b %Y')}  |  {len(reports)} stocks selected",
             f"{'='*75}"]

    for r in reports:
        t = r.tech
        f = r.fund
        lines.append(f"\n{'─'*75}")
        lines.append(f"  {r.symbol:<12} | {r.cap_category:<10} | Score: {r.composite_score:>3}/100 | Grade: {r.overall_grade} | {r.best_trade_type}")
        if t:
            lines.append(f"  CMP: ₹{t.close:<10} ATR: ₹{t.atr:<8} Trend: {t.trend:<12} RSI: {t.rsi}")
            lines.append(f"  Support: ₹{t.support:<10} Resistance: ₹{t.resistance}")

        if r.swing_pick and t and t.swing:
            s = t.swing
            lines.append(f"  [SWING]     Entry ₹{s.entry}  T1 ₹{s.target1}  T2 ₹{s.target2}  SL ₹{s.stop_loss}  R:R 1:{s.risk_reward}")
        if r.long_term_pick and t and t.long_term:
            s = t.long_term
            lines.append(f"  [LONG TERM] Entry ₹{s.entry}  T1 ₹{s.target1}  T2 ₹{s.target2}  SL ₹{s.stop_loss}  R:R 1:{s.risk_reward}")
        if r.intraday_pick and t and t.intraday:
            s = t.intraday
            lines.append(f"  [INTRADAY]  Entry ₹{s.entry}  T1 ₹{s.target1}  T2 ₹{s.target2}  SL ₹{s.stop_loss}  R:R 1:{s.risk_reward}")

        if f:
            lines.append(f"  Fundamentals: PE={f.pe_ratio} PB={f.pb_ratio} ROE={f.roe}% Margin={f.net_margin}% RevGrowth={f.revenue_growth_yoy}%")
            for flag in f.flags:
                lines.append(f"  {flag}")
        if t:
            for sig in t.signals[:4]:
                lines.append(f"  {sig}")

    lines.append(f"\n{'='*75}")
    lines.append("  Not financial advice. Do your own research.")
    lines.append(f"{'='*75}\n")
    return "\n".join(lines)
