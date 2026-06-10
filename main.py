"""
main.py — Trade Screener entry point

Usage:
  python main.py                          # scan all caps, all trade types
  python main.py --cap midcap             # midcap only
  python main.py --cap largecap --trade swing
  python main.py --cap smallcap --trade longterm --min-score 65
  python main.py --cap all --max 200 --workers 6
  python main.py --no-notify              # console output only
"""

import argparse
import asyncio
import logging
import os
import sys

from config import cfg
from screener.screener import run_screener
from screener.report_builder import format_console, format_telegram, format_html_email
from screener.notifier import send_telegram_message, send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(description="Indian Stock Techno-Fundamental Screener")
    p.add_argument("--cap",       default="all",
                   choices=["all", "largecap", "midcap", "smallcap"],
                   help="Market cap segment to scan")
    p.add_argument("--trade",     default="all",
                   choices=["all", "longterm", "swing", "intraday"],
                   help="Filter by trade type")
    p.add_argument("--min-score", default=55, type=int,
                   help="Minimum composite score (0-100)")
    p.add_argument("--max",       default=100, type=int,
                   help="Max stocks to scan per segment")
    p.add_argument("--workers",   default=4, type=int,
                   help="Parallel fetch threads")
    p.add_argument("--no-notify", action="store_true",
                   help="Print results only, skip notifications")
    return p.parse_args()


def main():
    args = parse_args()
    cfg.log_status()

    log.info(f"Starting scan: cap={args.cap}  trade={args.trade}  "
             f"min_score={args.min_score}  max={args.max}")

    # ── Run screener ───────────────────────────────────────────────────────────
    reports = run_screener(
        cap_filter   = args.cap,
        max_stocks   = args.max,
        min_score    = args.min_score,
        trade_filter = args.trade,
        workers      = args.workers,
    )

    # ── Console output (always) ────────────────────────────────────────────────
    print(format_console(reports))

    if not reports:
        log.info("No stocks matched the criteria today. Try lowering --min-score.")
        sys.exit(0)

    if args.no_notify:
        log.info("--no-notify flag set. Skipping notifications.")
        return

    # ── Telegram ───────────────────────────────────────────────────────────────
    if cfg.telegram_enabled:
        messages = format_telegram(reports, cap_filter=args.cap)

        async def _send_all():
            for msg in messages:
                await send_telegram_message(cfg.telegram_token, cfg.telegram_chat_id, msg)

        asyncio.run(_send_all())
    else:
        log.warning("Telegram not configured — set TELEGRAM_TOKEN and TELEGRAM_CHAT_ID in .env")

    # ── Email ──────────────────────────────────────────────────────────────────
    if cfg.email_enabled:
        html = format_html_email(reports, cap_filter=args.cap)
        send_email(
            sender      = cfg.email_sender,
            password    = cfg.email_password,
            recipient   = cfg.email_recipient,
            html_body   = html,
            subject     = f"Trade Screener — {len(reports)} pick(s) | {args.cap.upper()}",
        )
    else:
        log.warning("Email not configured — set EMAIL_SENDER / EMAIL_PASSWORD / EMAIL_RECIPIENT in .env")


if __name__ == "__main__":
    main()
