"""
config.py
Loads all configuration from environment variables (or a .env file).

Import this anywhere:
    from config import cfg
    print(cfg.telegram_token)
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


def _load_dotenv():
    """Load .env file if python-dotenv is installed."""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass  # dotenv is optional; env vars set directly work fine


@dataclass
class Config:
    # ── Telegram ───────────────────────────────────────────────────────────────
    telegram_token: Optional[str] = field(default=None)
    telegram_chat_id: Optional[str] = field(default=None)

    # ── Email ──────────────────────────────────────────────────────────────────
    email_sender: Optional[str] = field(default=None)
    email_password: Optional[str] = field(default=None)
    email_recipient: Optional[str] = field(default=None)
    email_smtp_host: str = field(default="smtp.gmail.com")
    email_smtp_port: int = field(default=465)

    # ── WhatsApp (Twilio) ──────────────────────────────────────────────────────
    twilio_account_sid: Optional[str] = field(default=None)
    twilio_auth_token: Optional[str] = field(default=None)
    twilio_whatsapp_from: Optional[str] = field(default=None)  # "whatsapp:+14155238886"
    twilio_whatsapp_to: Optional[str] = field(default=None)    # "whatsapp:+919876543210"

    # ── Screener settings ──────────────────────────────────────────────────────
    # Which stock universe to scan: "nifty50", "nifty_next50", "all"
    stock_universe: str = field(default="nifty50")

    # yfinance period for historical data: "3mo", "6mo", "1y", "2y"
    data_period: str = field(default="6mo")

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)

    @property
    def email_enabled(self) -> bool:
        return bool(self.email_sender and self.email_password and self.email_recipient)

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_whatsapp_from
            and self.twilio_whatsapp_to
        )

    def log_status(self):
        log.info(f"Notifications — Telegram: {'✓' if self.telegram_enabled else '✗'} | "
                 f"Email: {'✓' if self.email_enabled else '✗'} | "
                 f"WhatsApp: {'✓' if self.whatsapp_enabled else '✗'}")
        log.info(f"Universe: {self.stock_universe} | Period: {self.data_period}")


def load_config() -> Config:
    _load_dotenv()
    return Config(
        # Telegram
        telegram_token=os.getenv("TELEGRAM_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),

        # Email
        email_sender=os.getenv("EMAIL_SENDER"),
        email_password=os.getenv("EMAIL_PASSWORD"),
        email_recipient=os.getenv("EMAIL_RECIPIENT"),
        email_smtp_host=os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
        email_smtp_port=int(os.getenv("EMAIL_SMTP_PORT", "465")),

        # WhatsApp
        twilio_account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
        twilio_auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
        twilio_whatsapp_from=os.getenv("TWILIO_WHATSAPP_FROM"),
        twilio_whatsapp_to=os.getenv("TWILIO_WHATSAPP_TO"),

        # Screener
        stock_universe=os.getenv("STOCK_UNIVERSE", "nifty50"),
        data_period=os.getenv("DATA_PERIOD", "6mo"),
    )


# Singleton — import cfg everywhere
cfg = load_config()
