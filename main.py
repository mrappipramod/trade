"""
main.py — Trade Screener entry point

Usage:
  python main.py                                  # scan all caps
  python main.py --cap midcap --trade swing
  python main.py --single-stock TCS              # single stock analysis
  python main.py --single-stock RELIANCE --no-notify
"""

import argparse
import asyncio
import logging
import sys

from config import cfg
from screener.screener      import run_screener
from screener.single_stock  import analyse_single
from screener.report_builder import format_console, format_telegram, format_html_email
from screener.notifier       import send_telegram_message, send_email

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def parse_args():
    p = argparse.ArgumentParser(description="Indian Stock Techno-Fundamental Screener")
    p.add_argument("--cap",          default="all",
                   choices=["all", "largecap", "midcap", "smallcap"])
    p.add_argument("--trade",        default="all",
                   choices=["all", "longterm", "swing", "intraday"])
    p.add_argument("--min-score",    default=55,  type=int)
    p.add_argument("--max",          default=100, type=int)
    p.add_argument("--workers",      default=4,   type=int)
    p.add_argument("--single-stock", default="",  type=str,
                   help="Analyse a single stock by NSE symbol (e.g. TCS)")
    p.add_argument("--no-notify",    action="store_true")
    return p.parse_args()


async def broadcast(token, chat_ids, messages):
    for chat_id in chat_ids:
        log.info(f"Sending to Telegram group: {chat_id}")
        for msg in messages:
            await send_telegram_message(token, chat_id, msg)
    log.info(f"Broadcast complete → {len(chat_ids)} group(s)")


def main():
    args = parse_args()
    cfg.log_status()

    # ── Single stock mode ──────────────────────────────────────────────────────
    if args.single_stock:
        symbol = args.single_stock.upper().strip()
        log.info(f"Single stock analysis: {symbol}")
        report = analyse_single(symbol)
        if not report:
            log.error(f"Analysis failed for {symbol}")
            sys.exit(1)

        reports = [report]
        print(format_console(reports))

        if not args.no_notify:
            messages = format_telegram(reports, cap_filter=f"Single: {symbol}")
            if cfg.telegram_enabled:
                asyncio.run(broadcast(cfg.telegram_token, cfg.telegram_chat_ids, messages))
            if cfg.email_enabled:
                send_email(
                    sender    = cfg.email_sender,
                    password  = cfg.email_password,
                    recipient = cfg.email_recipient,
                    html_body = format_html_email(reports, cap_filter=symbol),
                    subject   = f"📊 {symbol} Analysis",
                )
        return

    # ── Screener mode ──────────────────────────────────────────────────────────
    log.info(f"Screener: cap={args.cap} trade={args.trade} min_score={args.min_score}")
    reports = run_screener(
        cap_filter   = args.cap,
        max_stocks   = args.max,
        min_score    = args.min_score,
        trade_filter = args.trade,
        workers      = args.workers,
    )

    print(format_console(reports))

    if not reports:
        log.info("No stocks matched. Try lowering --min-score.")
        sys.exit(0)

    if args.no_notify:
        return

    if cfg.telegram_enabled:
        messages = format_telegram(reports, cap_filter=args.cap)
        asyncio.run(broadcast(cfg.telegram_token, cfg.telegram_chat_ids, messages))
    else:
        log.warning("Telegram not configured — set TELEGRAM_TOKEN and TELEGRAM_CHAT_IDS")

    if cfg.email_enabled:
        send_email(
            sender    = cfg.email_sender,
            password  = cfg.email_password,
            recipient = cfg.email_recipient,
            html_body = format_html_email(reports, cap_filter=args.cap),
            subject   = f"📈 Trade Screener — {len(reports)} pick(s) | {args.cap.upper()}",
        )
    else:
        log.warning("Email not configured — set EMAIL_SENDER / EMAIL_PASSWORD / EMAIL_RECIPIENT")


if __name__ == "__main__":
    main()
