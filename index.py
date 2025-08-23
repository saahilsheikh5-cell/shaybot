import os
import telebot
from flask import Flask, request
import requests
import pandas as pd
import numpy as np
import talib

# ==============================
# CONFIG
# ==============================
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shaybot-13.onrender.com/" + BOT_TOKEN

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# ==============================
# WATCHLIST
# ==============================
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
    "PEPEUSDT", "BONKUSDT", "MEMEUSDT", "PUMPUSDT",
    "FARTCOINUSDT", "TRUMPUSDT", "VINEUSDT", "MAVIAUSDT", "YFIUSDT", "ADAUSDT", "LINKUSDT"
]

# ==============================
# GLOBAL SIGNAL TOGGLE
# ==============================
signals_on = True

# ==============================
# HELPERS
# ==============================
def fetch_klines(symbol, interval, limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=[
        "time", "open", "high", "low", "close", "volume",
        "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"
    ])
    df["close"] = df["close"].astype(float)
    return df

def analyze(symbol, interval):
    try:
        df = fetch_klines(symbol, interval)
        closes = df["close"].values

        rsi = talib.RSI(closes, timeperiod=14)
        macd, macdsignal, macdhist = talib.MACD(closes, 12, 26, 9)

        last_price = closes[-1]
        last_rsi = rsi[-1]
        last_macd = macd[-1]
        last_signal = macdsignal[-1]

        if last_rsi < 40 and last_macd > last_signal:
            return f"✅ BUY | Price: {last_price:.2f}, RSI={last_rsi:.2f} (MACD Bullish)"
        elif last_rsi > 60 and last_macd < last_signal:
            return f"❌ SELL | Price: {last_price:.2f}, RSI={last_rsi:.2f} (MACD Bearish)"
        else:
            return "No clear signal"
    except Exception:
        return "Error"

def get_top_movers():
    movers_1h, movers_24h = [], []
    for symbol in WATCHLIST:
        try:
            # 1h change (last vs first close of last 60m candles)
            df_1h = fetch_klines(symbol, "1m", 60)
            change_1h = (df_1h["close"].iloc[-1] - df_1h["close"].iloc[0]) / df_1h["close"].iloc[0] * 100

            # 24h change (from ticker stats)
            stats = requests.get("https://api.binance.com/api/v3/ticker/24hr", params={"symbol": symbol}).json()
            change_24h = float(stats["priceChangePercent"])

            movers_1h.append((symbol, change_1h))
            movers_24h.append((symbol, change_24h))
        except:
            continue

    top_1h = sorted(movers_1h, key=lambda x: abs(x[1]), reverse=True)[:5]
    top_24h = sorted(movers_24h, key=lambda x: abs(x[1]), reverse=True)[:5]

    msg = "🚀 Top Movers\n\n"
    msg += "⏱ 1 Hour Movers:\n" + "\n".join([f"{s}: {c:+.2f}%" for s, c in top_1h]) + "\n\n"
    msg += "📅 24 Hour Movers:\n" + "\n".join([f"{s}: {c:+.2f}%" for s, c in top_24h])
    return msg

# ==============================
# BOT COMMANDS
# ==============================
@bot.message_handler(commands=["start"])
def start(message):
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Technical Analysis", "🚀 Top Movers")
    markup.add("✅ Signals ON", "🛑 Signals OFF")
    bot.send_message(message.chat.id, "Welcome! Choose an option:", reply_markup=markup)

@bot.message_handler(func=lambda m: True)
def menu(message):
    global signals_on
    if message.text == "📊 Technical Analysis":
        text = "📊 Technical Analysis Signals:\n\n"
        for symbol in WATCHLIST:
            text += f"🔹 {symbol}\n"
            for tf in ["1m", "5m", "15m", "1h", "4h", "1d"]:
                sig = analyze(symbol, tf)
                text += f"   ⏱ {tf}: {sig}\n"
            text += "\n"
        bot.send_message(message.chat.id, text)

    elif message.text == "🚀 Top Movers":
        bot.send_message(message.chat.id, get_top_movers())

    elif message.text == "✅ Signals ON":
        signals_on = True
        bot.send_message(message.chat.id, "✅ Signals are now ON. You’ll start receiving alerts.")

    elif message.text == "🛑 Signals OFF":
        signals_on = False
        bot.send_message(message.chat.id, "🛑 Signals are now OFF. You won’t receive alerts.")

# ==============================
# FLASK WEBHOOK
# ==============================
@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    json_str = request.stream.read().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "ok", 200

@app.route("/")
def index():
    return "Bot is running!", 200

if __name__ == "__main__":
    # Remove old webhook, set new one
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


