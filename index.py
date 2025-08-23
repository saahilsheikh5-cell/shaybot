
import os
import telebot
import requests
import time
import threading
import numpy as np

# === CONFIG ===
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shaybot-13.onrender.com/" + BOT_TOKEN
bot = telebot.TeleBot(BOT_TOKEN)

# Default portfolio coins
portfolio = {"BTCUSDT": 0.5, "ETHUSDT": 2, "SOLUSDT": 50}
watchlist = set(portfolio.keys())

BASE_URL = "https://api.binance.com/api/v3"

# === Helper Functions ===
def fetch_price(symbol):
    try:
        r = requests.get(f"{BASE_URL}/ticker/24hr?symbol={symbol}", timeout=5).json()
        return float(r["lastPrice"]), float(r["priceChangePercent"])
    except Exception:
        return None, None

def fetch_klines(symbol, interval="1m", limit=100):
    try:
        url = f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit={limit}"
        data = requests.get(url, timeout=5).json()
        closes = [float(x[4]) for x in data]
        return closes
    except Exception:
        return []

def calc_rsi(prices, period=14):
    if len(prices) < period:
        return None
    deltas = np.diff(prices)
    gains = deltas[deltas > 0].sum() / period
    losses = -deltas[deltas < 0].sum() / period
    if losses == 0: return 100
    rs = gains / losses
    return 100 - (100 / (1 + rs))

def moving_average(prices, period=14):
    if len(prices) < period:
        return None
    return np.mean(prices[-period:])

def generate_signal(symbol, interval):
    prices = fetch_klines(symbol, interval)
    if not prices: return None
    rsi = calc_rsi(prices)
    ma = moving_average(prices)
    last_price = prices[-1]

    if rsi is None or ma is None:
        return None

    if rsi < 35 and last_price > ma:
        return f"BUY ✅ — {symbol} {interval} | Price: {last_price:.2f}, RSI={rsi:.2f}, MA={ma:.2f}"
    elif rsi > 70 and last_price < ma:
        return f"SELL ❌ — {symbol} {interval} | Price: {last_price:.2f}, RSI={rsi:.2f}, MA={ma:.2f}"
    else:
        return None

def top_movers():
    movers = []
    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]:
        _, change = fetch_price(sym)
        if change is not None:
            movers.append((sym, change))
    movers.sort(key=lambda x: abs(x[1]), reverse=True)
    return movers[:3]

# === Bot Commands ===
@bot.message_handler(commands=["start"])
def start(message):
    menu = ("📊 Portfolio\n"
            "📈 Live Prices\n"
            "📊 Technical Analysis\n"
            "🚀 Top Movers\n"
            "➕ Add Coin\n"
            "➖ Remove Coin\n"
            "🔔 Signals On")
    bot.send_message(message.chat.id, "Welcome! Choose an option:\n\n" + menu)

@bot.message_handler(func=lambda msg: msg.text == "📊 Portfolio")
def portfolio_handler(message):
    total = 0
    text = "📊 Your Portfolio:\n\n"
    for coin, qty in portfolio.items():
        price, change = fetch_price(coin)
        if price:
            value = qty * price
            total += value
            text += f"{coin[:-4]}: {qty} × ${price:.2f} = ${value:.2f} ({change:.2f}% 24h)\n"
        else:
            text += f"{coin}: Error fetching price\n"
    text += f"\n💰 Total Portfolio Value: ${total:.2f}"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda msg: msg.text == "📊 Technical Analysis")
def ta_handler(message):
    text = "📊 Technical Analysis:\n\n"
    for sym in watchlist:
        for interval in ["1m","5m","15m","1h"]:
            sig = generate_signal(sym, interval)
            if sig:
                text += sig + "\n"
            else:
                text += f"{sym} {interval}: No clear signal\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda msg: msg.text == "🚀 Top Movers")
def movers_handler(message):
    movers = top_movers()
    text = "🚀 Top Movers (1h):\n\n"
    for sym, chg in movers:
        text += f"{sym}: {chg:.2f}%\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda msg: msg.text == "➕ Add Coin")
def add_coin(message):
    bot.send_message(message.chat.id, "Send symbol (e.g., MATICUSDT)")
    bot.register_next_step_handler(message, save_coin)

def save_coin(message):
    symbol = message.text.upper()
    watchlist.add(symbol)
    bot.send_message(message.chat.id, f"{symbol} added to watchlist ✅")

@bot.message_handler(func=lambda msg: msg.text == "➖ Remove Coin")
def remove_coin(message):
    bot.send_message(message.chat.id, "Send symbol to remove")
    bot.register_next_step_handler(message, delete_coin)

def delete_coin(message):
    symbol = message.text.upper()
    if symbol in watchlist:
        watchlist.remove(symbol)
        bot.send_message(message.chat.id, f"{symbol} removed ❌")
    else:
        bot.send_message(message.chat.id, f"{symbol} not found in watchlist")

# === Background Signal Notifier ===
def signal_watcher():
    while True:
        for sym in watchlist:
            for interval in ["1m","5m","15m"]:
                sig = generate_signal(sym, interval)
                if sig:
                    bot.send_message(1263295916, "📢 " + sig)
        time.sleep(60)

threading.Thread(target=signal_watcher, daemon=True).start()

# === Webhook ===
from flask import Flask, request
app = Flask(__name__)

@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode("utf-8"))
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def index():
    return "Bot is running!", 200

if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



