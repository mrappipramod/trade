"""
notifier.py — Telegram, Email, WhatsApp notifications

Key functions (called from main.py):
  await send_telegram_message(token, chat_id, text)
  send_email(sender, password, recipient, html_body, subject)
  send_whatsapp(account_sid, auth_token, from_number, to_number, text)
"""

import logging
import smtplib
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger(__name__)


def _split_message(text: str, limit: int = 4000) -> list:
    """Split long text into chunks at newline boundaries."""
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


# ── Telegram ───────────────────────────────────────────────────────────────────
# Setup:
#   1. Message @BotFather → /newbot → copy the token
#   2. Start a chat with your bot, then visit:
#      https://api.telegram.org/bot<TOKEN>/getUpdates  →  find "chat":{"id": ...}
#   3. Set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID in your .env

async def send_telegram_message(token: str, chat_id: str, text: str) -> bool:
    """Send a single pre-formatted markdown message to Telegram."""
    try:
        from telegram import Bot
        from telegram.constants import ParseMode

        bot = Bot(token=token)
        chunks = _split_message(text, limit=4000)
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


# ── Email (Gmail / any SMTP) ───────────────────────────────────────────────────
# Setup (Gmail):
#   1. Enable 2-Step Verification on your Google account
#   2. Go to: myaccount.google.com/apppasswords → create App Password
#   3. Set EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECIPIENT in .env

def send_email(
    sender: str,
    password: str,
    recipient: str,
    html_body: str,
    subject: str = "",
    smtp_host: str = "smtp.gmail.com",
    smtp_port: int = 465,
) -> bool:
    """Send an HTML email."""
    try:
        today = date.today().strftime("%d %b %Y")
        if not subject:
            subject = f"📈 Trade Screener — {today}"

        plain_text = "See the HTML version of this email for the full screener report."

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = sender
        msg["To"]      = recipient

        msg.attach(MIMEText(plain_text, "plain"))
        msg.attach(MIMEText(html_body,  "html"))

        with smtplib.SMTP_SSL(smtp_host, smtp_port) as smtp:
            smtp.login(sender, password)
            smtp.send_message(msg)

        log.info(f"Email sent to {recipient}")
        return True

    except Exception as e:
        log.error(f"Email send failed: {e}")
        return False


# ── WhatsApp (Twilio) ──────────────────────────────────────────────────────────
# Setup:
#   1. Sign up at twilio.com → get Account SID and Auth Token
#   2. Join the WhatsApp sandbox: twilio.com/console/messaging/whatsapp/sandbox
#   3. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
#      TWILIO_WHATSAPP_FROM (e.g. "whatsapp:+14155238886")
#      TWILIO_WHATSAPP_TO   (e.g. "whatsapp:+919876543210")

def send_whatsapp(
    account_sid: str,
    auth_token: str,
    from_number: str,
    to_number: str,
    text: str,
) -> bool:
    """Send a WhatsApp message via Twilio."""
    try:
        from twilio.rest import Client

        client = Client(account_sid, auth_token)
        chunks = _split_message(text, limit=1500)
        for chunk in chunks:
            client.messages.create(body=chunk, from_=from_number, to=to_number)

        log.info(f"WhatsApp: sent {len(chunks)} message(s) to {to_number}")
        return True

    except ImportError:
        log.error("twilio not installed. Run: pip install twilio")
        return False
    except Exception as e:
        log.error(f"WhatsApp send failed: {e}")
        return False
