"""
config.py
Loads all configuration from environment variables (or a .env file).

Import this anywhere:
    from config import cfg
    print(cfg.telegram_chat_ids)   # list of all group IDs
"""

import os
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger(__name__)


def _load_dotenv():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


@dataclass
class Config:
    # ── Telegram ───────────────────────────────────────────────────────────────
    telegram_token: Optional[str] = field(default=None)

    # Comma-separated list of chat/group IDs in .env:
    #   TELEGRAM_CHAT_IDS=-5277461725,-1001234567890,987654321
    telegram_chat_ids: list = field(default_factory=list)

    # ── Email ──────────────────────────────────────────────────────────────────
    email_sender: Optional[str] = field(default=None)
    email_password: Optional[str] = field(default=None)
    email_recipient: Optional[str] = field(default=None)
    email_smtp_host: str = field(default="smtp.gmail.com")
    email_smtp_port: int = field(default=465)

    # ── WhatsApp (Twilio) ──────────────────────────────────────────────────────
    twilio_account_sid: Optional[str] = field(default=None)
    twilio_auth_token: Optional[str] = field(default=None)
    twilio_whatsapp_from: Optional[str] = field(default=None)
    twilio_whatsapp_to: Optional[str] = field(default=None)

    # ── Screener settings ──────────────────────────────────────────────────────
    stock_universe: str = field(default="nifty50")
    data_period: str = field(default="6mo")

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_ids)

    @property
    def email_enabled(self) -> bool:
        return bool(self.email_sender and self.email_password and self.email_recipient)

    @property
    def whatsapp_enabled(self) -> bool:
        return bool(
            self.twilio_account_sid and self.twilio_auth_token
            and self.twilio_whatsapp_from and self.twilio_whatsapp_to
        )

    def log_status(self):
        tg = f"✓ ({len(self.telegram_chat_ids)} group(s))" if self.telegram_enabled else "✗"
        log.info(f"Notifications — Telegram: {tg} | "
                 f"Email: {'✓' if self.email_enabled else '✗'} | "
                 f"WhatsApp: {'✓' if self.whatsapp_enabled else '✗'}")
        if self.telegram_enabled:
            for gid in self.telegram_chat_ids:
                log.info(f"  Telegram group: {gid}")
        log.info(f"Universe: {self.stock_universe} | Period: {self.data_period}")


def _parse_chat_ids(raw: str) -> list:
    """
    Parse comma-separated chat IDs from env var.
    Handles spaces, empty entries, and both positive and negative IDs.
    e.g. "-5277461725, -1001234567890, 987654321"  →  ['-5277461725', '-1001234567890', '987654321']
    """
    if not raw:
        return []
    return [cid.strip() for cid in raw.split(",") if cid.strip()]


def load_config() -> Config:
    _load_dotenv()

    # Support both old single ID (TELEGRAM_CHAT_ID) and new multi (TELEGRAM_CHAT_IDS)
    # so existing setups don't break
    single_id  = os.getenv("TELEGRAM_CHAT_ID", "")
    multi_ids  = os.getenv("TELEGRAM_CHAT_IDS", "")

    # Merge both: multi_ids takes priority; single_id is appended if not already present
    ids = _parse_chat_ids(multi_ids)
    if single_id and single_id not in ids:
        ids.append(single_id)

    return Config(
        telegram_token    = os.getenv("TELEGRAM_TOKEN"),
        telegram_chat_ids = ids,

        email_sender      = os.getenv("EMAIL_SENDER"),
        email_password    = os.getenv("EMAIL_PASSWORD"),
        email_recipient   = os.getenv("EMAIL_RECIPIENT"),
        email_smtp_host   = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com"),
        email_smtp_port   = int(os.getenv("EMAIL_SMTP_PORT", "465")),

        twilio_account_sid   = os.getenv("TWILIO_ACCOUNT_SID"),
        twilio_auth_token    = os.getenv("TWILIO_AUTH_TOKEN"),
        twilio_whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM"),
        twilio_whatsapp_to   = os.getenv("TWILIO_WHATSAPP_TO"),

        stock_universe = os.getenv("STOCK_UNIVERSE", "nifty50"),
        data_period    = os.getenv("DATA_PERIOD", "6mo"),
    )


# Singleton — import cfg everywhere
cfg = load_config()
