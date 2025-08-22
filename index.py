import telebot
from telebot import types
import requests
import pandas as pd
import numpy as np

BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
CRYPTOCOMPARE_API_KEY = "93eb38b2e64b3481bd12239e84f23738216a84109433ac772c3f37aeb38bc209"

bot = telebot.TeleBot(BOT_TOKEN)

# ========== Helper Functions ==========

def get_prices():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            "ids": "bitcoin,ethereum,solana",
            "vs_currencies": "usd"
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        btc = data.get("bitcoin", {}).get("usd", "N/A")
        eth = data.get("ethereum", {}).get("usd", "N/A")
        sol = data.get("solana", {}).get("usd", "N/A")
        return f"₿ BTC: {btc}\nΞ ETH: {eth}\n◎ SOL: {sol}"
    except Exception as e:
        return f"⚠️ Error fetching prices: {e}"

def get_movers():
    try:
        url = "https://api.coingecko.com/api/v3/coins/markets"
        params = {
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 10,
            "page": 1,
            "price_change_percentage": "24h"
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if not isinstance(data, list):
            return "⚠️ Error fetching movers"
        movers = sorted(data, key=lambda x: x.get("price_change_percentage_24h", 0), reverse=True)
        top_gainers = movers[:3]
        top_losers = movers[-3:]
        msg = "📈 Top Gainers (24h):\n"
        for c in top_gainers:
            msg += f"{c['symbol'].upper()}: {c['price_change_percentage_24h']:.2f}%\n"
        msg += "\n📉 Top Losers (24h):\n"
        for c in top_losers:
            msg += f"{c['symbol'].upper()}: {c['price_change_percentage_24h']:.2f}%\n"
        return msg
    except Exception as e:
        return f"⚠️ Error fetching movers: {e}"

def fetch_candles(symbol="BTC", interval="1m", limit=100):
    try:
        url = f"https://min-api.cryptocompare.com/data/v2/histo{interval[:-1]}"
        params = {
            "fsym": symbol.upper(),
            "tsym": "USD",
            "limit": limit,
            "api_key": CRYPTOCOMPARE_API_KEY
        }
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if "Data" not in data or "Data" not in data["Data"]:
            return None
        df = pd.DataFrame(data["Data"]["Data"])
        if df.empty:
            return None
        return df
    except Exception as e:
        return None

def calculate_rsi(prices, period=14):
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def technical_analysis(symbol="BTC", interval="1m"):
    df = fetch_candles(symbol, interval)
    if df is None:
        return f"⚠️ TA error for {symbol}{interval}"
    close = df["close"]
    rsi = calculate_rsi(close).iloc[-1]
    ema9 = close.ewm(span=9).mean().iloc[-1]
    ema21 = close.ewm(span=21).mean().iloc[-1]
    macd_line = close.ewm(span=12).mean() - close.ewm(span=26).mean()
    signal_line = macd_line.ewm(span=9).mean()
    macd = macd_line.iloc[-1] - signal_line.iloc[-1]

    signal = []
    if rsi < 30:
        signal.append("Oversold → Buy")
    elif rsi > 70:
        signal.append("Overbought → Sell")
    if ema9 > ema21:
        signal.append("EMA Bullish")
    else:
        signal.append("EMA Bearish")
    if macd > 0:
        signal.append("MACD Bullish")
    else:
        signal.append("MACD Bearish")

    return f"📊 TA for {symbol}{interval}:\nRSI: {rsi:.2f}\nEMA9: {ema9:.2f}, EMA21: {ema21:.2f}\nMACD: {macd:.2f}\nSignals: {', '.join(signal)}"

# ========== Bot Handlers ==========

@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📈 Live Prices", "📊 Technical Analysis")
    markup.row("🚀 Top Movers", "⚙️ Settings")
    bot.send_message(message.chat.id, "Welcome to SaahilCryptoBot 🚀\nUse the buttons below:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📈 Live Prices")
def handle_prices(message):
    bot.send_message(message.chat.id, get_prices())

@bot.message_handler(func=lambda m: m.text == "🚀 Top Movers")
def handle_movers(message):
    bot.send_message(message.chat.id, get_movers())

@bot.message_handler(func=lambda m: m.text == "📊 Technical Analysis")
def handle_ta(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("BTC 1m", "BTC 5m", "BTC 15m", "BTC 1h")
    markup.row("ETH 1m", "ETH 5m", "ETH 15m", "ETH 1h")
    markup.row("SOL 1m", "SOL 5m", "SOL 15m", "SOL 1h")
    bot.send_message(message.chat.id, "📉 Choose market & timeframe:", reply_markup=markup)

@bot.message_handler(func=lambda m: any(x in m.text for x in ["BTC", "ETH", "SOL"]))
def handle_ta_choice(message):
    try:
        parts = message.text.split()
        symbol, interval = parts[0], parts[1]
        bot.send_message(message.chat.id, technical_analysis(symbol, interval))
    except Exception:
        bot.send_message(message.chat.id, "⚠️ Invalid TA request")

@bot.message_handler(func=lambda m: m.text == "⚙️ Settings")
def handle_settings(message):
    bot.send_message(message.chat.id, "⚙️ Settings menu coming soon!")

print("Bot is running...")
bot.infinity_polling()
