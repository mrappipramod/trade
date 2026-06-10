"""
notifier.py
Send stock scan results via Telegram, Email, or WhatsApp (Twilio).

Setup instructions are in the comments of each function.
"""

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

log = logging.getLogger(__name__)


# ── Message formatters ─────────────────────────────────────────────────────────

def _format_result_row(stock: dict) -> str:
    """Single line summary for a stock result."""
    base = f"• *{stock['symbol']}* | ₹{stock['close']} | {stock['strategy']}"

    # Append relevant metrics depending on strategy
    extras = []
    if "rsi" in stock:
        extras.append(f"RSI {stock['rsi']}")
    if "vol_ratio" in stock:
        extras.append(f"Vol×{stock['vol_ratio']}")
    if "ema9" in stock:
        extras.append(f"EMA9 {stock['ema9']} / EMA21 {stock['ema21']}")
    if "histogram" in stock:
        extras.append(f"MACD hist {stock['histogram']}")
    if "breakout_pct" in stock:
        extras.append(f"+{stock['breakout_pct']}% breakout")
    if "pct_b" in stock:
        extras.append(f"%B {stock['pct_b']}")

    if extras:
        base += " | " + ", ".join(extras)
    return base


def _build_message(stocks: list) -> tuple[str, str]:
    """
    Returns (plain_text, markdown_text) for the full report.
    Telegram uses markdown_text; email uses plain_text.
    """
    today = date.today().strftime("%d %b %Y")
    header = f"📊 *Trade Screener — {today}*\n"
    header += f"_{len(stocks)} signal(s) found across {len({s['symbol'] for s in stocks})} stock(s)_\n"

    # Group by strategy
    by_strategy: dict[str, list] = {}
    for s in stocks:
        by_strategy.setdefault(s["strategy"], []).append(s)

    md_lines = [header]
    plain_lines = [f"Trade Screener — {today}", f"{len(stocks)} signal(s) found\n"]

    for strategy, items in by_strategy.items():
        md_lines.append(f"\n*{strategy}*")
        plain_lines.append(f"\n{strategy}")
        for item in items:
            row = _format_result_row(item)
            md_lines.append(row)
            plain_lines.append(row.replace("*", "").replace("_", ""))

    md_lines.append("\n_Data via NSE • Not financial advice_")
    plain_lines.append("\nData via NSE • Not financial advice")

    return "\n".join(plain_lines), "\n".join(md_lines)


# ── Telegram ───────────────────────────────────────────────────────────────────
# Setup:
#   1. Message @BotFather on Telegram → /newbot → copy the token
#   2. Start a chat with your new bot
#   3. Visit: https://api.telegram.org/bot<TOKEN>/getUpdates
#      Look for "chat":{"id": <YOUR_CHAT_ID>}
#   4. Set env vars: TELEGRAM_TOKEN and TELEGRAM_CHAT_ID

async def send_telegram(token: str, chat_id: str, stocks: list) -> bool:
    """Send scan results to a Telegram chat."""
    try:
        from telegram import Bot
        from telegram.constants import ParseMode

        _, md_text = _build_message(stocks)

        bot = Bot(token=token)
        # Telegram has a 4096 char limit per message; split if needed
        chunks = _split_message(md_text, limit=4000)
        for chunk in chunks:
            await bot.send_message(
                chat_id=chat_id,
                text=chunk,
                parse_mode=ParseMode.MARKDOWN,
            )
        log.info(f"Telegram: sent {len(chunks)} message(s) to chat {chat_id}")
        return True

    except ImportError:
        log.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
        return False
    except Exception as e:
        log.error(f"Telegram send failed: {e}")
        return False


def _split_message(text: str, limit: int = 4000) -> list:
    """Split a long message into chunks at newline boundaries."""
    if len(text) <= limit:
        return [text]
    chunks, current = [], []
    for line in text.split("\n"):
        if sum(len(l) + 1 for l in current) + len(line) > limit:
            chunks.append("\n".join(current))
            current = []
        current.append(line)
    if current:
        chunks.append("\n".join(current))
    return chunks


# ── Email (Gmail / any SMTP) ───────────────────────────────────────────────────
# Setup (Gmail):
#   1. Enable 2-Step Verification on your Google account
#   2. Go to: myaccount.google.com/apppasswords
#   3. Create an App Password → copy the 16-char password
#   4. Set env vars: EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT

def send_email(
    sender: str,
    password: str,
    recipient: str,
    stocks: list,
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 465,
) -> bool:
    """Send scan results via email (HTML + plain text)."""
    try:
        today = date.today().strftime("%d %b %Y")
        plain_text, _ = _build_message(stocks)
        html_body = _build_html_email(stocks, today)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"📈 Trade Screener — {len(stocks)} signal(s) | {today}"
        msg["From"] = sender
        msg["To"] = recipient

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)

        log.info(f"Email sent to {recipient}")
        return True

    except Exception as e:
        log.error(f"Email send failed: {e}")
        return False


def _build_html_email(stocks: list, today: str) -> str:
    """Build a clean HTML email body."""
    by_strategy: dict[str, list] = {}
    for s in stocks:
        by_strategy.setdefault(s["strategy"], []).append(s)

    rows_html = ""
    for strategy, items in by_strategy.items():
        rows_html += f"""
        <tr><td colspan="4" style="background:#1a1a2e;color:#e0e0ff;
            padding:8px 12px;font-weight:bold;font-size:13px;">
            {strategy}
        </td></tr>"""
        for item in items:
            extras = []
            if "rsi" in item:
                extras.append(f"RSI {item['rsi']}")
            if "vol_ratio" in item:
                extras.append(f"Vol×{item['vol_ratio']}")
            if "ema9" in item:
                extras.append(f"EMA9 {item['ema9']} / EMA21 {item['ema21']}")
            if "breakout_pct" in item:
                extras.append(f"+{item['breakout_pct']}% breakout")
            if "histogram" in item:
                extras.append(f"MACD hist {item['histogram']}")
            if "pct_b" in item:
                extras.append(f"%B {item['pct_b']}")

            signal_color = "#22c55e" if item["signal"] == "BUY" else "#ef4444"
            rows_html += f"""
            <tr>
                <td style="padding:8px 12px;font-weight:bold;">{item['symbol']}</td>
                <td style="padding:8px 12px;">₹{item['close']}</td>
                <td style="padding:8px 12px;color:#888;">{', '.join(extras)}</td>
                <td style="padding:8px 12px;color:{signal_color};font-weight:bold;">
                    {item['signal']}
                </td>
            </tr>"""

    return f"""<!DOCTYPE html>
<html>
<body style="font-family:Arial,sans-serif;background:#f4f4f8;padding:20px;margin:0;">
  <div style="max-width:640px;margin:auto;background:#fff;border-radius:8px;
              box-shadow:0 2px 8px rgba(0,0,0,.1);overflow:hidden;">
    <div style="background:#0f172a;color:#fff;padding:20px 24px;">
      <h2 style="margin:0;">📊 Trade Screener</h2>
      <p style="margin:4px 0 0;color:#94a3b8;">{today} • {len(stocks)} signal(s) across
         {len({s['symbol'] for s in stocks})} stock(s)</p>
    </div>
    <div style="padding:16px 24px;">
      <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
          <tr style="border-bottom:2px solid #e2e8f0;color:#64748b;">
            <th style="padding:8px 12px;text-align:left;">Symbol</th>
            <th style="padding:8px 12px;text-align:left;">Close</th>
            <th style="padding:8px 12px;text-align:left;">Indicators</th>
            <th style="padding:8px 12px;text-align:left;">Signal</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    <div style="background:#f8fafc;padding:12px 24px;font-size:12px;color:#94a3b8;
                border-top:1px solid #e2e8f0;">
      Data via NSE • For informational purposes only • Not financial advice
    </div>
  </div>
</body>
</html>"""


# ── WhatsApp (Twilio) ──────────────────────────────────────────────────────────
# Setup:
#   1. Sign up at twilio.com → get Account SID and Auth Token
#   2. Join the WhatsApp sandbox: twilio.com/console/messaging/whatsapp/sandbox
#      (or apply for a production number)
#   3. Set env vars: TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
#                    TWILIO_WHATSAPP_FROM (e.g. "whatsapp:+14155238886")
#                    TWILIO_WHATSAPP_TO   (e.g. "whatsapp:+919876543210")

def send_whatsapp(
    account_sid: str,
    auth_token: str,
    from_number: str,
    to_number: str,
    stocks: list,
) -> bool:
    """Send scan results via WhatsApp using Twilio."""
    try:
        from twilio.rest import Client

        plain_text, _ = _build_message(stocks)
        # WhatsApp messages have a 1600 char limit
        chunks = _split_message(plain_text, limit=1500)

        client = Client(account_sid, auth_token)
        for chunk in chunks:
            client.messages.create(
                body=chunk,
                from_=from_number,
                to=to_number,
            )
        log.info(f"WhatsApp: sent {len(chunks)} message(s) to {to_number}")
        return True

    except ImportError:
        log.error("twilio not installed. Run: pip install twilio")
        return False
    except Exception as e:
        log.error(f"WhatsApp send failed: {e}")
        return False


# ── Quick test ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Test with dummy data
    sample = [
        {"symbol": "TCS",     "strategy": "RSI Oversold + Volume Spike",
         "close": 3542.10, "rsi": 32.1, "vol_ratio": 1.8, "signal": "BUY"},
        {"symbol": "INFY",    "strategy": "EMA 9/21 Golden Cross",
         "close": 1821.50, "ema9": 1818.0, "ema21": 1815.0, "signal": "BUY"},
        {"symbol": "RELIANCE","strategy": "52-Week High Breakout",
         "close": 2980.0, "prev_52w_high": 2950.0, "breakout_pct": 1.02, "signal": "BUY"},
    ]
    plain, md = _build_message(sample)
    print(md)
