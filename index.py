import time
import threading
import telebot
from telebot import types
import requests
import pandas as pd
import numpy as np

# Hardcoded credentials
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shaybot-13.onrender.com/" + BOT_TOKEN

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# Track user signal preferences
user_signals = {}

# Binance API endpoints
BASE_URL = "https://api.binance.com"
KLINES_ENDPOINT = "/api/v3/klines"
TICKER_24HR_ENDPOINT = "/api/v3/ticker/24hr"

# Watchlist (main + meme coins)
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT",
    "PEPEUSDT", "BONKUSDT", "DOGEUSDT", "SHIBUSDT", "FLOKIUSDT",
    "MEMEUSDT", "TRUMPUSDT", "VINEUSDT", "PUMPUSDT", "FARTCOINUSDT",
    "MAVIAUSDT", "ADAUSDT", "LINKUSDT", "YFIUSDT"
]

# Helper: fetch klines
def get_klines(symbol, interval, limit=100):
    url = BASE_URL + KLINES_ENDPOINT
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"Error fetching klines {symbol}-{interval}: {e}")
        return []

# RSI calculation
def calculate_rsi(prices, period=14):
    deltas = np.diff(prices)
    if len(deltas) < period:
        return 50
    seed = deltas[:period]
    up = seed[seed >= 0].sum() / period
    down = -seed[seed < 0].sum() / period
    rs = up / down if down != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    return rsi

# MACD calculation
def calculate_macd(prices, slow=26, fast=12, signal=9):
    exp1 = pd.Series(prices).ewm(span=fast, adjust=False).mean()
    exp2 = pd.Series(prices).ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    signal_line = macd.ewm(span=signal, adjust=False).mean()
    return macd.iloc[-1], signal_line.iloc[-1]

# Generate signal
def generate_signal(symbol, interval):
    klines = get_klines(symbol, interval, 100)
    if not klines:
        return "No data"
    closes = [float(k[4]) for k in klines]
    price = closes[-1]
    rsi = calculate_rsi(closes)
    macd, signal_line = calculate_macd(closes)
    trend = "Bullish" if macd > signal_line else "Bearish"

    if rsi < 35 and macd > signal_line:
        return f"✅ BUY | Price: {price:.2f}, RSI={rsi:.2f} (MACD {trend})"
    elif rsi > 65 and macd < signal_line:
        return f"❌ SELL | Price: {price:.2f}, RSI={rsi:.2f} (MACD {trend})"
    else:
        return "No clear signal"

# Handle /start
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    user_signals[chat_id] = True  # default ON
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("📊 Technical Analysis", callback_data="technical_analysis"),
        types.InlineKeyboardButton("🚀 Top Movers", callback_data="top_movers")
    )
    keyboard.row(
        types.InlineKeyboardButton("✅ Signals ON", callback_data="signals_on"),
        types.InlineKeyboardButton("❌ Signals OFF", callback_data="signals_off")
    )
    bot.send_message(chat_id, "Welcome to the Crypto Bot Dashboard 🚀", reply_markup=keyboard)

# Handle buttons
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    chat_id = call.message.chat.id

    if call.data == "technical_analysis":
        text = "📊 Technical Analysis Signals:\n\n"
        timeframes = ["1m", "5m", "15m", "1h", "4h", "1d"]
        for sym in WATCHLIST:
            text += f"🔹 {sym}\n"
            for tf in timeframes:
                signal = generate_signal(sym, tf)
                text += f"   ⏱ {tf}: {signal}\n"
            text += "\n"
        bot.send_message(chat_id, text)

    elif call.data == "top_movers":
        text = "🚀 Top Movers\n\n"
        # 1H movers
        changes_1h = {}
        for sym in WATCHLIST:
            klines = get_klines(sym, "1h", 2)
            if len(klines) == 2:
                open_price = float(klines[0][1])
                close_price = float(klines[1][4])
                change = ((close_price - open_price) / open_price) * 100
                changes_1h[sym] = change
        top_1h = sorted(changes_1h.items(), key=lambda x: x[1], reverse=True)[:5]
        text += "⏱ 1 Hour Movers:\n" + "\n".join([f"{s}: {c:+.2f}%" for s, c in top_1h]) + "\n\n"

        # 24H movers
        r = requests.get(BASE_URL + TICKER_24HR_ENDPOINT, timeout=10).json()
        changes_24h = {x["symbol"]: float(x["priceChangePercent"]) for x in r if x["symbol"] in WATCHLIST}
        top_24h = sorted(changes_24h.items(), key=lambda x: x[1], reverse=True)[:5]
        text += "📅 24 Hour Movers:\n" + "\n".join([f"{s}: {c:+.2f}%" for s, c in top_24h])

        bot.send_message(chat_id, text)

    elif call.data == "signals_on":
        user_signals[chat_id] = True
        bot.send_message(chat_id, "✅ Signals are now ON")

    elif call.data == "signals_off":
        user_signals[chat_id] = False
        bot.send_message(chat_id, "❌ Signals are now OFF")

# Background task for signals
def signal_loop():
    while True:
        for chat_id, active in list(user_signals.items()):
            if active:
                for sym in WATCHLIST:
                    for tf in ["1m", "5m", "15m"]:
                        signal = generate_signal(sym, tf)
                        if "BUY" in signal or "SELL" in signal:
                            bot.send_message(chat_id, f"📢 {sym} ({tf}): {signal}")
        time.sleep(60)

threading.Thread(target=signal_loop, daemon=True).start()

# Run bot
if WEBHOOK_URL:
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
else:
    bot.polling(none_stop=True)

