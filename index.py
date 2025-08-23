import telebot
from telebot import types
import requests
import pandas as pd
import ta
import time
import threading

# === BOT CONFIG ===
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shaybot-13.onrender.com/" + BOT_TOKEN

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")

# === SIGNAL STATE ===
signals_enabled = True

# === SYMBOLS TO MONITOR ===
symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT",
           "BNBUSDT", "PEPEUSDT", "BONKUSDT", "MEMEUSDT",
           "PUMPUSDT", "FARTCOINUSDT", "TRUMPUSDT", "VINEUSDT",
           "MAVIAUSDT", "YFIUSDT", "ADAUSDT", "LINKUSDT"]

# === TIMEFRAMES ===
timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]

# === FETCH PRICE DATA ===
def fetch_klines(symbol, interval, limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        data = requests.get(url, timeout=5).json()
        df = pd.DataFrame(data, columns=[
            "time", "open", "high", "low", "close", "volume",
            "close_time", "qav", "trades", "tbbav", "tbqav", "ignore"
        ])
        df["close"] = pd.to_numeric(df["close"])
        return df
    except Exception:
        return None

# === GENERATE TECHNICAL SIGNALS ===
def get_signal(symbol, interval):
    df = fetch_klines(symbol, interval)
    if df is None or df.empty:
        return "Error"

    try:
        df["rsi"] = ta.momentum.RSIIndicator(df["close"], window=14).rsi()
        df["macd"] = ta.trend.MACD(df["close"]).macd()
        rsi = df["rsi"].iloc[-1]
        macd = df["macd"].iloc[-1]
        price = df["close"].iloc[-1]

        if rsi < 30 and macd > 0:
            return f"✅ BUY | Price: {price:.2f}, RSI={rsi:.2f} (MACD Bullish)"
        elif rsi > 70 and macd < 0:
            return f"❌ SELL | Price: {price:.2f}, RSI={rsi:.2f} (MACD Bearish)"
        else:
            return "No clear signal"
    except Exception:
        return "Error"

# === SIGNALS BROADCAST ===
def broadcast_signals():
    while True:
        if signals_enabled:
            message = "📊 Technical Analysis Signals:\n\n"
            for symbol in symbols:
                message += f"🔹 {symbol}\n"
                for tf in timeframes:
                    signal = get_signal(symbol, tf)
                    message += f"   ⏱ {tf}: {signal}\n"
                message += "\n"
            try:
                bot.send_message(chat_id, message)
            except:
                pass
        time.sleep(300)  # every 5 minutes

# === START COMMAND ===
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
@bot.message_handler(func=lambda msg: msg.text == "📈 Technical Analysis")
def ta_handler(message):
    text = "📊 Technical Analysis Signals:\n\n"
    for symbol in symbols[:5]:  # show top 5 for quick response
        text += f"🔹 {symbol}\n"
        for tf in timeframes:
            signal = get_signal(symbol, tf)
            text += f"   ⏱ {tf}: {signal}\n"
        text += "\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda msg: msg.text == "💰 Live Prices")
def live_price_handler(message):
    text = "💰 Live Prices:\n\n"
    for symbol in symbols[:10]:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        try:
            price = float(requests.get(url, timeout=5).json()["price"])
            text += f"{symbol}: {price:.2f}\n"
        except:
            text += f"{symbol}: Error\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda msg: msg.text == "🚀 Top Movers")
def movers_handler(message):
    text = "🚀 Top Movers\n\n"

    for tf, interval in [("1 Hour", "1h"), ("24 Hour", "1d")]:
        movers = []
        for symbol in symbols[:10]:
            df = fetch_klines(symbol, interval, 2)
            if df is not None and len(df) >= 2:
                try:
                    p1, p2 = df["close"].iloc[-2], df["close"].iloc[-1]
                    change = (p2 - p1) / p1 * 100
                    movers.append((symbol, change))
                except:
                    continue
        movers.sort(key=lambda x: abs(x[1]), reverse=True)
        text += f"⏱ {tf} Movers:\n"
        for sym, ch in movers[:5]:
            text += f"{sym}: {ch:+.2f}%\n"
        text += "\n"

    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda msg: msg.text == "✅ Signals ON")
def enable_signals(message):
    global signals_enabled
    signals_enabled = True
    bot.send_message(message.chat.id, "✅ Signals have been ENABLED.")

@bot.message_handler(func=lambda msg: msg.text == "❌ Signals OFF")
def disable_signals(message):
    global signals_enabled
    signals_enabled = False
    bot.send_message(message.chat.id, "❌ Signals have been DISABLED.")

# === BACKGROUND THREAD ===
threading.Thread(target=broadcast_signals, daemon=True).start()

# === START BOT ===
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)

print("Bot is running with Webhook...")





