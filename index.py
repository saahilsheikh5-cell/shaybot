import os
import time
import threading
from flask import Flask, request
import telebot
from telebot import types
import requests
import numpy as np

# ---- Configuration ----
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shaybot-13.onrender.com/" + BOT_TOKEN
ADMIN_ID = 1263295916  # your Telegram user ID
PRICE_CACHE_INTERVAL = 60  # seconds
SIGNAL_CHECK_INTERVAL = 60  # seconds for automatic signals

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SaahilCryptoBot/1.0)"}

# Initial portfolio (coin symbol: amount)
portfolio = {
    "BTCUSDT": 0.5,
    "ETHUSDT": 2,
    "SOLUSDT": 50
}

# Cached prices
cached_prices = {}

# ---- Logging ----
def log(msg):
    print(f"[SaahilBot] {msg}", flush=True)

# ---- Binance helpers ----
def http_get_json(url, params=None, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"HTTP GET error {url}: {e}")
        return None

def get_price_binance(symbol):
    url = "https://api.binance.com/api/v3/ticker/price"
    stats_url = "https://api.binance.com/api/v3/ticker/24hr"
    p = http_get_json(url, params={"symbol": symbol})
    s = http_get_json(stats_url, params={"symbol": symbol})
    if not p:
        return None
    try:
        price = float(p.get("price", 0))
        change = float(s.get("priceChangePercent", 0)) if s else 0.0
        return {"price": price, "change": change}
    except Exception as e:
        log(f"parse price error {symbol}: {e}")
        return None

def get_klines_binance(symbol, interval="1h", limit=100):
    url = "https://api.binance.com/api/v3/klines"
    data = http_get_json(url, params={"symbol": symbol, "interval": interval, "limit": limit})
    if not data or not isinstance(data, list):
        return []
    try:
        closes = [float(c[4]) for c in data]
        return closes
    except Exception as e:
        log(f"parse klines error {symbol}: {e}")
        return []

# ---- Indicators ----
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    deltas = np.diff(prices)
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    avg_gain = gains[-period:].mean()
    avg_loss = losses[-period:].mean()
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return round(float(rsi), 2)

def calculate_ma(prices, period=14):
    if len(prices) < period:
        return None
    return round(float(np.mean(prices[-period:])), 2)

# ---- Price caching ----
def update_price_cache():
    while True:
        for symbol in portfolio:
            data = get_price_binance(symbol)
            cached_prices[symbol] = data
        time.sleep(PRICE_CACHE_INTERVAL)

threading.Thread(target=update_price_cache, daemon=True).start()

# ---- Build texts ----
def build_portfolio_text():
    text_lines = ["📊 Your Portfolio:\n"]
    total = 0.0
    for symbol, amount in portfolio.items():
        data = cached_prices.get(symbol)
        if not data:
            text_lines.append(f"{symbol}: Error fetching price")
            continue
        price = data['price']
        change = data['change']
        value = price * amount
        total += value
        text_lines.append(f"{symbol}: {amount} × ${price:,.2f} = ${value:,.2f} ({change:+.2f}% 24h)")
    text_lines.append(f"\n💰 Total Portfolio Value: ${total:,.2f}")
    return "\n".join(text_lines)

def generate_signals_text(interval="1h"):
    lines = []
    for symbol in portfolio:
        closes = get_klines_binance(symbol, interval=interval, limit=50)
        if not closes:
            lines.append(f"{symbol}: Error fetching data")
            continue
        rsi = calculate_rsi(closes)
        ma14 = calculate_ma(closes)
        current = closes[-1]
        verdict = "HOLD ⚠️"
        # Trend detection
        if closes[-1] > ma14 and rsi < 70:
            verdict = "BUY ✅"
        elif closes[-1] < ma14 and rsi > 30:
            verdict = "SELL ❌"
        lines.append(f"{symbol}: {verdict} — Price: ${current:,.2f}, RSI14={rsi}, MA14=${ma14}")
    return "\n".join(lines)

def get_top_movers(limit=5):
    data = http_get_json("https://api.binance.com/api/v3/ticker/24hr")
    if not data:
        return "Error fetching top movers"
    try:
        usdt = [x for x in data if x.get('symbol','').endswith('USDT')]
        top = sorted(usdt, key=lambda x: float(x.get('priceChangePercent',0)), reverse=True)[:limit]
        lines = []
        for t in top:
            lines.append(f"{t['symbol']}: ${float(t['lastPrice']):,.4f} ({float(t['priceChangePercent']):+.2f}% 24h)")
        return "\n".join(lines)
    except Exception as e:
        log(f"parse top movers error: {e}")
        return "Error fetching top movers"

# ---- Telegram Handlers ----
@bot.message_handler(commands=['start'])
def cmd_start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('Live Prices', callback_data='live_prices'),
        types.InlineKeyboardButton('Portfolio', callback_data='portfolio'),
        types.InlineKeyboardButton('Technical Analysis', callback_data='technical'),
        types.InlineKeyboardButton('Top Movers', callback_data='top_movers'),
        types.InlineKeyboardButton('Signals', callback_data='signals'),
        types.InlineKeyboardButton('Add Coin', callback_data='add_coin'),
        types.InlineKeyboardButton('Remove Coin', callback_data='remove_coin')
    )
    bot.send_message(message.chat.id, '📈 Welcome to SaahilCryptoBot Dashboard', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    try:
        if call.data == 'live_prices':
            text = build_portfolio_text()
        elif call.data == 'portfolio':
            text = build_portfolio_text()
        elif call.data == 'technical':
            # Let user choose interval
            markup = types.InlineKeyboardMarkup()
            for intr in ['1m','5m','15m','1h']:
                markup.add(types.InlineKeyboardButton(intr, callback_data=f"technical_{intr}"))
            bot.send_message(call.message.chat.id,"Select interval:",reply_markup=markup)
            return
        elif call.data.startswith('technical_'):
            interval = call.data.split('_')[1]
            lines = []
            for symbol in portfolio:
                closes = get_klines_binance(symbol, interval=interval, limit=50)
                ma14 = calculate_ma(closes)
                rsi = calculate_rsi(closes)
                lines.append(f"{symbol}: RSI14={rsi if rsi else 'N/A'}, MA14=${ma14 if ma14 else 'N/A'}")
            text = f"📊 Technical Analysis ({interval})\n" + "\n".join(lines)
        elif call.data == 'top_movers':
            text = '🚀 Top Movers 24h\n\n' + get_top_movers()
        elif call.data == 'signals':
            text = '📢 Trading Signals\n\n' + generate_signals_text()
        elif call.data == 'add_coin':
            msg = bot.send_message(call.message.chat.id,"Send symbol to add (e.g., ADAUSDT):")
            bot.register_next_step_handler(msg, add_coin)
            return
        elif call.data == 'remove_coin':
            markup = types.InlineKeyboardMarkup()
            for symbol in portfolio:
                markup.add(types.InlineKeyboardButton(symbol, callback_data=f"remove_{symbol}"))
            bot.send_message(call.message.chat.id,"Select coin to remove:",reply_markup=markup)
            return
        elif call.data.startswith("remove_"):
            symbol = call.data.split("_")[1]
            portfolio.pop(symbol, None)
            bot.send_message(call.message.chat.id,f"{symbol} removed from portfolio")
            return
        else:
            text = "Unknown action"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('Back', callback_data='live_prices'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception as e:
        log(f"Callback error: {e}")
        try:
            bot.answer_callback_query(call.id, 'Error processing request')
        except: pass

def add_coin(message):
    symbol = message.text.upper()
    portfolio[symbol] = 0
    bot.send_message(message.chat.id,f"{symbol} added to portfolio with 0 amount")

# ---- Periodic Signals ----
def send_periodic_signals():
    while True:
        try:
            text = '📢 Periodic Trading Signals\n\n' + generate_signals_text()
            bot.send_message(ADMIN_ID,text)
            log("Periodic signals sent")
        except Exception as e:
            log(f"Error sending periodic signals: {e}")
        time.sleep(SIGNAL_CHECK_INTERVAL)

threading.Thread(target=send_periodic_signals,daemon=True).start()

# ---- Webhook ----
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook_handler():
    try:
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
    except Exception as e:
        log(f'Webhook processing error: {e}')
    return '!', 200

@app.route('/health', methods=['GET'])
def health():
    return 'Bot is running',200

@app.route('/', methods=['GET'])
def set_webhook():
    try:
        bot.remove_webhook()
        bot.set_webhook(url=WEBHOOK_URL)
        log(f'Webhook set: {WEBHOOK_URL}')
        return f'Webhook set: {WEBHOOK_URL}', 200
    except Exception as e:
        log(f'Error setting webhook: {e}')
        return f'Error setting webhook: {e}', 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT',5000))
    log(f"Starting bot on port {port}")
    app.run(host='0.0.0.0', port=port)


