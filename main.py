"""
Trade - Indian Stock Market Screener
Entry point: fetches data, runs analysis, sends notifications.
"""

import os
import logging
from screener.data_fetcher import fetch_all
from screener.analysis import screen_stocks
from screener.notifier import send_telegram, send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def main():
    log.info("=== Trade Screener Started ===")

    # 1. Fetch data
    log.info("Fetching stock data...")
    data = fetch_all()
    log.info(f"Fetched data for {len(data)} stocks.")

    # 2. Run analysis
    log.info("Running analysis...")
    selected = screen_stocks(data)
    log.info(f"Selected {len(selected)} stocks.")

    if not selected:
        log.info("No stocks matched the criteria today.")
        return

    # 3. Send notifications
    telegram_token = os.getenv("TELEGRAM_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")
    email_sender = os.getenv("EMAIL_SENDER")
    email_password = os.getenv("EMAIL_PASSWORD")
    email_recipient = os.getenv("EMAIL_RECIPIENT")

    if telegram_token and telegram_chat_id:
        log.info("Sending Telegram notification...")
        import asyncio
        asyncio.run(send_telegram(telegram_token, telegram_chat_id, selected))
    else:
        log.warning("Telegram credentials not set — skipping.")

    if email_sender and email_password and email_recipient:
        log.info("Sending email notification...")
        send_email(email_sender, email_password, email_recipient, selected)
    else:
        log.warning("Email credentials not set — skipping.")

    log.info("=== Screener Done ===")


if __name__ == "__main__":
    main()
