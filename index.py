import os
import telebot
from telebot import types
import requests
import pandas as pd
import numpy as np
import threading
import time
from flask import Flask, request

# === BOT CONFIG ===
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shaybot-14.onrender.com/" + BOT_TOKEN
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# === SIGNAL STATE ===
signals_enabled = True
chat_id = None

# === SYMBOLS & TIMEFRAMES ===
symbols = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
    "BNBUSDT", "PEPEUSDT", "BONKUSDT", "MEMEUSDT",
    "PUMPUSDT", "FARTCOINUSDT", "TRUMPUSDT", "VINEUSDT",
    "MAVIAUSDT", "YFIUSDT", "ADAUSDT", "LINKUSDT"
]
timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]

# === CACHE CONFIG ===
klines_cache = {}
KL_CACHE_DURATION = 60
signal_cache = {}
SIGNAL_CACHE_DURATION = 60

# === FETCH KLINES WITH CACHE ===
def fetch_klines(symbol, interval, limit=100):
    now = time.time()
    key = (symbol, interval)
    if key in klines_cache and now - klines_cache[key]["timestamp"] < KL_CACHE_DURATION:
        return klines_cache[key]["data"]

    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        data = requests.get(url, timeout=5).json()
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"
        ])
        df["close"] = pd.to_numeric(df["close"])
        klines_cache[key] = {"data": df, "timestamp": now}
        return df
    except:
        return None

# === TECHNICAL SIGNALS ===
def calc_rsi(prices, period=14):
    if len(prices) < period: return None
    deltas = np.diff(prices)
    gain = np.mean([d for d in deltas if d > 0] or [0])
    loss = -np.mean([d for d in deltas if d < 0] or [0])
    if loss == 0: return 100
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calc_macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow + signal: return None, None
    ema_fast = np.mean(prices[-fast:])
    ema_slow = np.mean(prices[-slow:])
    macd = ema_fast - ema_slow
    signal_line = np.mean(prices[-signal:])
    return macd, signal_line

def get_signal(symbol, interval):
    now = time.time()
    key = (symbol, interval)
    if key in signal_cache and now - signal_cache[key]["timestamp"] < SIGNAL_CACHE_DURATION:
        return signal_cache[key]["signal"]

    df = fetch_klines(symbol, interval)
    if df is None or df.empty:
        signal = "Error"
    else:
        try:
            close = df["close"].values
            rsi = calc_rsi(close)
            macd, signal_line = calc_macd(close)
            price = close[-1]
            if rsi is None or macd is None:
                signal = "No clear signal"
            elif rsi < 30 and macd > signal_line:
                signal = f"✅ BUY | Price: {price:.2f}, RSI={rsi:.2f} (MACD Bullish)"
            elif rsi > 70 and macd < signal_line:
                signal = f"❌ SELL | Price: {price:.2f}, RSI={rsi:.2f} (MACD Bearish)"
            else:
                signal = "No clear signal"
        except:
            signal = "Error"

    signal_cache[key] = {"signal": signal, "timestamp": now}
    return signal

# === SIGNAL BROADCAST ===
def broadcast_signals():
    global chat_id
    while True:
        if signals_enabled and chat_id:
            message = "📊 Technical Analysis Signals:\n\n"
            for symbol in symbols[:10]:
                message += f"🔹 {symbol}\n"
                for tf in timeframes:
                    message += f"   ⏱ {tf}: {get_signal(symbol, tf)}\n"
                message += "\n"
            try:
                bot.send_message(chat_id, message)
            except:
                pass
        time.sleep(300)  # every 5 minutes

# === BOT COMMANDS ===
@bot.message_handler(commands=["start"])
def start(message):
    global chat_id
    chat_id = message.chat.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📈 Technical Analysis", "💰 Live Prices")
    markup.row("✅ Signals ON", "❌ Signals OFF")
    markup.row("🚀 Top Movers")
    bot.send_message(chat_id, "Welcome! Choose an option:", reply_markup=markup)

# === BUTTON HANDLERS ===
@bot.message_handler(func=lambda m: m.text == "📈 Technical Analysis")
def ta_handler(message):
    text = "📊 Technical Analysis Signals:\n\n"
    for symbol in symbols[:10]:
        text += f"🔹 {symbol}\n"
        for tf in timeframes:
            text += f"   ⏱ {tf}: {get_signal(symbol, tf)}\n"
        text += "\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "💰 Live Prices")
def live_prices(message):
    text = "💰 Live Prices:\n\n"
    for symbol in symbols[:10]:
        try:
            price = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}", timeout=5).json()["price"])
            text += f"{symbol}: {price:.2f}\n"
        except:
            text += f"{symbol}: Error\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "🚀 Top Movers")
def movers_handler(message):
    text = "🚀 Top Movers\n\n"
    for label, interval in [("1 Hour", "1h"), ("24 Hour", "1d")]:
        movers = []
        for sym in symbols[:10]:
            df = fetch_klines(sym, interval, 2)
            if df is not None and len(df) >= 2:
                try:
                    p1, p2 = df["close"].iloc[-2], df["close"].iloc[-1]
                    movers.append((sym, (p2 - p1)/p1*100))
                except:
                    continue
        movers.sort(key=lambda x: abs(x[1]), reverse=True)
        text += f"⏱ {label} Movers:\n"
        for sym, ch in movers[:5]:
            text += f"{sym}: {ch:+.2f}%\n"
        text += "\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "✅ Signals ON")
def signals_on(message):
    global signals_enabled
    signals_enabled = True
    bot.send_message(message.chat.id, "✅ Signals have been ENABLED.")

@bot.message_handler(func=lambda m: m.text == "❌ Signals OFF")
def signals_off(message):
    global signals_enabled
    signals_enabled = False
    bot.send_message(message.chat.id, "❌ Signals have been DISABLED.")

# === START SIGNAL BROADCAST THREAD ===
threading.Thread(target=broadcast_signals, daemon=True).start()

# === FLASK SERVER FOR WEBHOOK ===
server = Flask(__name__)

@server.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    json_str = request.stream.read().decode("utf-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

@server.route("/")
def index():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    return "Bot is running with Webhook!", 200

# === RUN SERVER ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    server.run(host="0.0.0.0", port=port)







