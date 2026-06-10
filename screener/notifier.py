# Telegram
import telegram

async def send_telegram(bot_token, chat_id, stocks):
    bot = telegram.Bot(token=bot_token)
    msg = "📊 *Today's Picks*\n\n"
    for s in stocks:
        msg += f"• `{s['symbol']}` | RSI: {s['rsi']} | ₹{s['close']}\n"
    await bot.send_message(chat_id=chat_id, text=msg, parse_mode="Markdown")

# Email (Gmail)
import smtplib
from email.mime.text import MIMEText

def send_email(sender, password, recipient, stocks):
    body = "\n".join([f"{s['symbol']} | RSI: {s['rsi']} | ₹{s['close']}" for s in stocks])
    msg = MIMEText(body)
    msg["Subject"] = "📈 Daily Stock Picks"
    msg["From"] = sender
    msg["To"] = recipient
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(sender, password)
        smtp.send_message(msg)
