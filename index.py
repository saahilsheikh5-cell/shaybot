
import os
from flask import Flask, request
import telebot
from telebot import types
import requests
import numpy as np

BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

portfolio_data = {
    "Bitcoin": {"amount": 0.5, "symbol": "BTCUSDT"},
    "Ethereum": {"amount": 2, "symbol": "ETHUSDT"},
    "Solana": {"amount": 50, "symbol": "SOLUSDT"}
}

HEADERS = {"User-Agent": "Mozilla/5.0"}

def get_price(symbol):
    try:
        url_price = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}"
        url_24h = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
        price_data = requests.get(url_price, headers=HEADERS, timeout=15).json()
        stats = requests.get(url_24h, headers=HEADERS, timeout=15).json()
        return {"price": float(price_data["price"]), "change": float(stats.get("priceChangePercent", 0))}
    except Exception as e:
        print(f"Error fetching price for {symbol}: {e}")
        return None

def get_historical_prices(symbol, limit=50):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=1d&limit={limit}"
        data = requests.get(url, headers=HEADERS, timeout=15).json()
        closes = [float(candle[4]) for candle in data]
        return closes
    except Exception as e:
        print(f"Error fetching historical for {symbol}: {e}")
        return []

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    ups = deltas[deltas > 0].sum() / period
    downs = -deltas[deltas < 0].sum() / period
    rs = ups / downs if downs != 0 else 0
    rsi = 100 - (100 / (1 + rs))
    return round(rsi, 2)

def calculate_ma(prices, period=14):
    if len(prices) < period:
        return None
    return round(np.mean(prices[-period:]), 2)

def generate_signals():
    signals = ""
    for coin, data in portfolio_data.items():
        prices = get_historical_prices(data["symbol"])
        if not prices:
            signals += f"{coin}: Error fetching data\n"
            continue
        rsi = calculate_rsi(prices)
        ma = calculate_ma(prices)
        current_price = prices[-1]
        if rsi is None or ma is None:
            signals += f"{coin}: Not enough data\n"
            continue
        if rsi < 30 or current_price < ma:
            signals += f"{coin}: Buy ✅ (Price: ${current_price:.2f}, RSI: {rsi})\n"
        elif rsi > 70 or current_price > ma:
            signals += f"{coin}: Sell ❌ (Price: ${current_price:.2f}, RSI: {rsi})\n"
        else:
            signals += f"{coin}: Hold ⚠️ (Price: ${current_price:.2f}, RSI: {rsi})\n"
    return signals

def build_portfolio_text():
    text = "📊 Your Portfolio:\n\n"
    total_value = 0
    for coin, data in portfolio_data.items():
        price_data = get_price(data["symbol"])
        if price_data:
            price = price_data["price"]
            change = price_data["change"]
            value = price * data["amount"]
            total_value += value
            text += f"{coin}: {data['amount']} × ${price:.2f} = ${value:.2f} ({change:+.2f}% 24h)\n"
        else:
            text += f"{coin}: Error fetching price\n"
    text += f"\n💰 Total Portfolio Value: ${total_value:.2f}"
    return text

def get_top_movers(limit=5):
    try:
        url = "https://api.binance.com/api/v3/ticker/24hr"
        data = requests.get(url, headers=HEADERS, timeout=15).json()
        movers = sorted(data, key=lambda x: float(x.get("priceChangePercent", 0)), reverse=True)
        text = ""
        count = 0
        for coin in movers:
            if coin["symbol"].endswith("USDT"):
                text += f'{coin["symbol"]}: ${float(coin["lastPrice"]):.2f} ({float(coin["priceChangePercent"]):+.2f}% 24h)\n'
                count += 1
            if count >= limit:
                break
        return text
    except Exception as e:
        print(f"Error fetching top movers: {e}")
        return "Error fetching top movers"

@bot.message_handler(commands=["start"])
def start_command(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Live Prices", callback_data="live_prices"))
    markup.add(types.InlineKeyboardButton("Technical Analysis", callback_data="technical_analysis"))
    markup.add(types.InlineKeyboardButton("Top Movers", callback_data="top_movers"))
    markup.add(types.InlineKeyboardButton("Signals", callback_data="signals"))
    markup.add(types.InlineKeyboardButton("Settings", callback_data="settings"))
    bot.send_message(message.chat.id, "📈 Welcome to SaahilCryptoBot Dashboard:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "live_prices":
        text = build_portfolio_text()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Back to Dashboard", callback_data="dashboard"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "technical_analysis":
        text = "📊 Technical Analysis (sample data):\n\n"
        for coin in portfolio_data.keys():
            prices = get_historical_prices(portfolio_data[coin]["symbol"])
            ma14 = calculate_ma(prices)
            rsi = calculate_rsi(prices)
            text += f"{coin}: RSI14={rsi if rsi else 'N/A'}, MA14=${ma14 if ma14 else 'N/A'}\n"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Back to Dashboard", callback_data="dashboard"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "top_movers":
        text = "🚀 Top Movers 24h:\n\n" + get_top_movers()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Back to Dashboard", callback_data="dashboard"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "signals":
        text = "📢 Trading Signals:\n\n" + generate_signals()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Back to Dashboard", callback_data="dashboard"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "settings":
        text = "⚙️ Settings:\n- Add/Remove coins (future update)\n- Notifications (future update)"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Back to Dashboard", callback_data="dashboard"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data == "dashboard":
        start_command(call.message)

@app.route("/" + BOT_TOKEN, methods=["POST"])
def webhook_handler():
    try:
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
    except Exception as e:
        print("Webhook error:", e)
    return "!", 200

@app.route("/")
def set_webhook():
    WEBHOOK_URL = "https://shaybot-10.onrender.com/" + BOT_TOKEN
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    return "Webhook set!", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

