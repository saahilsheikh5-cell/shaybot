
import os
import telebot
import requests
import time
import threading
import numpy as np
from flask import Flask, request
from telebot import types

# === CONFIG ===
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shaybot-13.onrender.com/" + BOT_TOKEN
bot = telebot.TeleBot(BOT_TOKEN)

# Default portfolio and watchlist
portfolio = {"BTCUSDT": 0.5, "ETHUSDT": 2, "SOLUSDT": 50}
watchlist = set(portfolio.keys())

BASE_URL = "https://api.binance.com/api/v3"

# === HELPER FUNCTIONS ===
def fetch_price(symbol):
    try:
        r = requests.get(f"{BASE_URL}/ticker/24hr?symbol={symbol}", timeout=5).json()
        return float(r["lastPrice"]), float(r["priceChangePercent"])
    except:
        return None, None

def fetch_klines(symbol, interval="1m", limit=100):
    try:
        url = f"{BASE_URL}/klines?symbol={symbol}&interval={interval}&limit={limit}"
        data = requests.get(url, timeout=5).json()
        closes = [float(x[4]) for x in data]
        return closes
    except:
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

def calc_macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow + signal:
        return None, None, None
    fast_ma = np.mean(prices[-fast:])
    slow_ma = np.mean(prices[-slow:])
    macd = fast_ma - slow_ma
    signal_line = np.mean([np.mean(prices[-(slow+i):]) for i in range(signal)])
    hist = macd - signal_line
    return macd, signal_line, hist

def generate_signal(symbol, interval):
    prices = fetch_klines(symbol, interval)
    if not prices:
        return None
    rsi = calc_rsi(prices)
    macd, signal_line, hist = calc_macd(prices)
    last_price = prices[-1]
    if rsi is None or macd is None:
        return None

    # RSI signals
    if rsi < 30: base_signal = "💚 STRONG BUY"
    elif rsi < 40: base_signal = "✅ BUY"
    elif rsi > 70: base_signal = "💔 STRONG SELL"
    elif rsi > 60: base_signal = "❌ SELL"
    else: return None

    # MACD trend
    trend = ""
    if macd > signal_line: trend = " (MACD Bullish)"
    elif macd < signal_line: trend = " (MACD Bearish)"

    return f"{base_signal} — {symbol} {interval} | Price: {last_price:.2f}, RSI={rsi:.2f}{trend}"

def top_movers(limit=5):
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    movers_1h, movers_24h = [], []

    for sym in symbols:
        _, change = fetch_price(sym)
        if change is not None:
            movers_1h.append((sym, change))
            movers_24h.append((sym, change))  # Using same as placeholder

    movers_1h = sorted(movers_1h, key=lambda x: abs(x[1]), reverse=True)[:limit]
    movers_24h = sorted(movers_24h, key=lambda x: abs(x[1]), reverse=True)[:limit]

    msg = "🚀 *Top Movers*\n\n"
    msg += "⏱ *1 Hour Movers:*\n"
    for sym, chg in movers_1h: msg += f"{sym}: {chg:+.2f}%\n"
    msg += "\n📅 *24 Hour Movers:*\n"
    for sym, chg in movers_24h: msg += f"{sym}: {chg:+.2f}%\n"
    return msg

def get_portfolio_summary():
    total = 0
    text = "📊 *Your Portfolio:*\n\n"
    for coin, qty in portfolio.items():
        price, change = fetch_price(coin)
        if price:
            value = qty * price
            total += value
            text += f"{coin[:-4]}: {qty} × ${price:.2f} = ${value:.2f} ({change:.2f}% 24h)\n"
        else: text += f"{coin}: Error fetching price\n"
    text += f"\n💰 Total Portfolio Value: ${total:.2f}"
    return text

def get_signals_text():
    text = "📊 *Technical Analysis Signals*\n\n"
    for sym in watchlist:
        text += f"🔹 {sym}\n"
        for interval in ["1m","5m","15m","1h","4h"]:
            sig = generate_signal(sym, interval)
            if sig: clean_sig = sig.split("—")[0].strip() + " | " + sig.split("|")[1].strip()
            else: clean_sig = "No clear signal"
            text += f"   ⏱ {interval}: {clean_sig}\n"
        text += "\n"
    return text

# === DASHBOARD ===
@bot.message_handler(commands=["start","dashboard"])
def dashboard(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📊 Portfolio", callback_data="portfolio"),
        types.InlineKeyboardButton("📈 Live Prices", callback_data="live_prices"),
        types.InlineKeyboardButton("📊 Technical Analysis", callback_data="technical_analysis"),
        types.InlineKeyboardButton("🚀 Top Movers", callback_data="top_movers"),
        types.InlineKeyboardButton("➕ Add Coin", callback_data="add_coin"),
        types.InlineKeyboardButton("➖ Remove Coin", callback_data="remove_coin"),
        types.InlineKeyboardButton("🔔 Signals On/Off", callback_data="toggle_signals"),
    )
    markup.add(types.InlineKeyboardButton("🔄 Refresh Dashboard", callback_data="refresh_dashboard"))
    bot.send_message(message.chat.id, "📌 *Crypto Dashboard*\n\nChoose an option:", reply_markup=markup, parse_mode="Markdown")

# === CALLBACK HANDLERS ===
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "refresh_dashboard":
        bot.answer_callback_query(call.id, "Refreshing Dashboard... 🔄")
        try: bot.delete_message(call.message.chat.id, call.message.message_id)
        except: pass
        dashboard(call.message)

    elif call.data == "portfolio" or call.data == "refresh_portfolio":
        bot.answer_callback_query(call.id, "Refreshing Portfolio... 🔄")
        text = get_portfolio_summary()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh Portfolio", callback_data="refresh_portfolio"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "top_movers" or call.data == "refresh_movers":
        bot.answer_callback_query(call.id, "Refreshing Movers... 🔄")
        text = top_movers()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Refresh Movers", callback_data="refresh_movers"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data == "technical_analysis" or call.data == "refresh_signals":
        bot.answer_callback_query(call.id, "Refreshing Signals... 🔄")
        text = get_signals_text()
        markup = types.InlineKeyboardMarkup()
        last_sym = list(watchlist)[-1]
        markup.add(
            types.InlineKeyboardButton("📊 TradingView", url=f"https://www.tradingview.com/chart/?symbol=BINANCE:{last_sym}"),
            types.InlineKeyboardButton("❌ Remove", callback_data=f"remove_{last_sym}")
        )
        markup.add(types.InlineKeyboardButton("🔄 Refresh Signals", callback_data="refresh_signals"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, parse_mode="Markdown", reply_markup=markup)

    elif call.data.startswith("remove_"):
        symbol = call.data.replace("remove_","")
        if symbol in watchlist:
            watchlist.remove(symbol)
            bot.answer_callback_query(call.id, f"{symbol} removed ✅")
            bot.send_message(call.message.chat.id, f"{symbol} removed ❌")
        else:
            bot.answer_callback_query(call.id, "Symbol not found ❌")

# === ADD/REMOVE COIN ===
@bot.message_handler(func=lambda msg: msg.text == "➕ Add Coin")
def add_coin(message):
    bot.send_message(message.chat.id, "Send symbol (e.g., MATICUSDT)")
    bot.register_next_step_handler(message, save_coin)

def save_coin(message):
    symbol = message.text.upper()
    watchlist.add(symbol)
    bot.send_message(message.chat.id, f"{symbol} added ✅")

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
        bot.send_message(message.chat.id, f"{symbol} not found ❌")

# === BACKGROUND SIGNAL ALERTS ===
def send_signals(chat_id=1263295916):
    alert_text = "📢 Signal Update\n\n"
    has_signal = False

    for sym in watchlist:
        sym_text = f"🔹 {sym}\n"
        coin_has_signal = False

        for interval in ["1m","5m","15m","1h","4h"]:
            sig = generate_signal(sym, interval)
            if sig:
                clean_sig = sig.split("—")[0].strip() + " | " + sig.split("|")[1].strip()
                sym_text += f"   ⏱ {interval}: {clean_sig}\n"
                coin_has_signal = True
            else:
                sym_text += f"   ⏱ {interval}: No clear signal\n"

        if coin_has_signal:
            alert_text += sym_text + "\n"
            has_signal = True

    if has_signal:
        markup = types.InlineKeyboardMarkup()
        last_sym = list(watchlist)[-1]
        markup.add(
            types.InlineKeyboardButton("📊 TradingView", url=f"https://www.tradingview.com/chart/?symbol=BINANCE:{last_sym}"),
            types.InlineKeyboardButton("❌ Remove", callback_data=f"remove_{last_sym}")
        )
        markup.add(types.InlineKeyboardButton("🔄 Refresh Now", callback_data="refresh_signals"))
        bot.send_message(chat_id, alert_text, reply_markup=markup)

def signal_watcher():
    while True:
        send_signals()
        time.sleep(60)

threading.Thread(target=signal_watcher, daemon=True).start()

# === WEBHOOK SETUP ===
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
