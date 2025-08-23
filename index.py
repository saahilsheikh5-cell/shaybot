import os
import json
import time
import requests
import pandas as pd
import ta
import telebot
import threading

# === CONFIG ===
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shaybot-13.onrender.com/" + BOT_TOKEN
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# === STATE PERSISTENCE ===
STATE_FILE = "signal_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"signal_active": True}  # default ON

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

state = load_state()
signal_active = state.get("signal_active", True)

# === SYMBOLS ===
symbols = ["BTCUSDT","ETHUSDT","SOLUSDT","XRPUSDT","BNBUSDT",
           "PEPEUSDT","BONKUSDT","MEMEUSDT","TRUMPUSDT","ADAUSDT",
           "LINKUSDT","YFIUSDT"]

# === FETCH PRICE DATA ===
def get_klines(symbol, interval="1m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        data = requests.get(url, timeout=5).json()
        df = pd.DataFrame(data, columns=[
            "t","o","h","l","c","v","ct","q","n","tb","tq","i"
        ])
        df["c"] = df["c"].astype(float)
        return df
    except:
        return None

# === TECHNICAL ANALYSIS ===
def analyze(symbol, interval):
    df = get_klines(symbol, interval)
    if df is None or df.empty:
        return "Error"

    close = df["c"]
    rsi = ta.momentum.RSIIndicator(close, window=14).rsi().iloc[-1]
    macd = ta.trend.MACD(close).macd_diff().iloc[-1]
    price = close.iloc[-1]

    # Loosened thresholds
    if rsi < 45 and macd > 0:
        return f"✅ BUY | Price: {price:.2f}, RSI={rsi:.2f} (MACD Bullish)"
    elif rsi > 55 and macd < 0:
        return f"❌ SELL | Price: {price:.2f}, RSI={rsi:.2f} (MACD Bearish)"
    else:
        return "No clear signal"

# === TELEGRAM HANDLERS ===
@bot.message_handler(commands=["start"])
def start(msg):
    menu = telebot.types.InlineKeyboardMarkup()
    menu.add(telebot.types.InlineKeyboardButton("📊 Technical Analysis", callback_data="ta"))
    menu.add(telebot.types.InlineKeyboardButton("🚀 Top Movers", callback_data="movers"))
    menu.add(telebot.types.InlineKeyboardButton("💰 Live Price", callback_data="price"))
    menu.add(telebot.types.InlineKeyboardButton("✅ Signals ON", callback_data="sig_on"))
    menu.add(telebot.types.InlineKeyboardButton("⛔ Signals OFF", callback_data="sig_off"))
    bot.send_message(msg.chat.id, "Welcome! Choose an option 👇", reply_markup=menu)

@bot.callback_query_handler(func=lambda call: True)
def menu_handler(call):
    global signal_active, state

    if call.data == "ta":
        text = "📊 Technical Analysis Signals:\n\n"
        for sym in symbols:
            text += f"🔹 {sym}\n"
            for tf in ["1m","5m","15m","1h","4h","1d"]:
                res = analyze(sym, tf)
                text += f"   ⏱ {tf}: {res}\n"
            text += "\n"
        bot.send_message(call.message.chat.id, text)

    elif call.data == "movers":
        movers_text = "🚀 Top Movers\n\n"
        for tf in ["1h","24h"]:
            movers_text += f"⏱ {tf.upper()} Movers:\n"
            for sym in symbols:
                df = get_klines(sym, "1h" if tf=="1h" else "1d")
                if df is None: continue
                pct = ((df["c"].iloc[-1] / df["c"].iloc[0]) - 1) * 100
                movers_text += f"{sym}: {pct:+.2f}%\n"
            movers_text += "\n"
        bot.send_message(call.message.chat.id, movers_text)

    elif call.data == "price":
        text = "💰 Live Prices:\n\n"
        for sym in symbols:
            df = get_klines(sym, "1m")
            if df is None: continue
            price = df["c"].iloc[-1]
            text += f"{sym}: {price:.2f}\n"
        bot.send_message(call.message.chat.id, text)

    elif call.data == "sig_on":
        signal_active = True
        state["signal_active"] = True
        save_state(state)
        bot.send_message(call.message.chat.id, "✅ Signals turned ON")

    elif call.data == "sig_off":
        signal_active = False
        state["signal_active"] = False
        save_state(state)
        bot.send_message(call.message.chat.id, "⛔ Signals turned OFF")

# === BACKGROUND SIGNAL MONITOR ===
def monitor_signals():
    global signal_active
    while True:
        if signal_active:
            for sym in symbols:
                res = analyze(sym, "5m")
                if "BUY" in res or "SELL" in res:
                    bot.send_message(
                        7638935379,  # replace with your chat_id if only for you
                        f"📢 Signal Alert: {sym} ({res})"
                    )
        time.sleep(60)  # check every minute

threading.Thread(target=monitor_signals, daemon=True).start()

# === START BOT ===
bot.remove_webhook()
bot.set_webhook(url=WEBHOOK_URL)




