
import os
import time
import threading
from flask import Flask, request
import telebot
from telebot import types
import requests
import numpy as np

# ---- Configuration (hardcoded as requested) ----
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shaybot-13.onrender.com/" + BOT_TOKEN
ADMIN_ID = 1263295916  # your Telegram user id to receive periodic signals
SIGNAL_INTERVAL_SECONDS = 3600  # 1 hour

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; SaahilCryptoBot/1.0)"}

portfolio = {
    "Bitcoin": {"symbol": "BTCUSDT", "amount": 0.5},
    "Ethereum": {"symbol": "ETHUSDT", "amount": 2},
    "Solana": {"symbol": "SOLUSDT", "amount": 50}
}

def log(msg):
    # centralized logging to stdout so Render logs show it
    print(f"[SaahilBot] {msg}", flush=True)

# ---- Binance helpers ----
def http_get_json(url, params=None, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, params=params, timeout=timeout)
        log(f"GET {r.url} -> {r.status_code} ({len(r.content)} bytes)")
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log(f"HTTP GET error for {url} params={params}: {e}")
        return None

def get_price_binance(symbol):
    # symbol like BTCUSDT
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

def get_klines_binance(symbol, limit=50):
    url = "https://api.binance.com/api/v3/klines"
    data = http_get_json(url, params={"symbol": symbol, "interval": "1d", "limit": limit})
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

# ---- Build texts ----
def build_portfolio_text():
    text_lines = ["📊 Your Portfolio:\n"] 
    total = 0.0
    for name, info in portfolio.items():
        data = get_price_binance(info['symbol'])
        if not data:
            text_lines.append(f"{name}: Error fetching price")
            continue
        price = data['price']
        change = data['change']
        value = price * info.get('amount', 0)
        total += value
        text_lines.append(f"{name}: {info.get('amount',0)} × ${price:,.2f} = ${value:,.2f} ({change:+.2f}% 24h)")
    text_lines.append(f"\n💰 Total Portfolio Value: ${total:,.2f}")
    return "\n".join(text_lines)

def get_top_movers(limit=5):
    url = "https://api.binance.com/api/v3/ticker/24hr"
    data = http_get_json(url)
    if not data or not isinstance(data, list):
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

def generate_signals_text():
    lines = []
    for name, info in portfolio.items():
        closes = get_klines_binance(info['symbol'], limit=60)
        if not closes:
            lines.append(f"{name}: Error fetching data")
            continue
        rsi = calculate_rsi(closes, period=14)
        ma14 = calculate_ma(closes, period=14)
        current = closes[-1]
        if rsi is None or ma14 is None:
            lines.append(f"{name}: Not enough data")
            continue
        verdict = "HOLD ⚠️"
        if rsi < 30 or current < ma14:
            verdict = "BUY ✅"
        elif rsi > 70 or current > ma14:
            verdict = "SELL ❌"
        lines.append(f"{name}: {verdict} — Price: ${current:,.2f}, RSI14={rsi}, MA14=${ma14}")
    return "\n".join(lines)

# ---- Telegram handlers ----
@bot.message_handler(commands=['start'])
def cmd_start(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(types.InlineKeyboardButton('Live Prices', callback_data='live_prices'),
               types.InlineKeyboardButton('Technical Analysis', callback_data='technical'),
               types.InlineKeyboardButton('Top Movers', callback_data='top_movers'),
               types.InlineKeyboardButton('Signals', callback_data='signals'),
               types.InlineKeyboardButton('Settings', callback_data='settings'))
    bot.send_message(message.chat.id, '📈 Welcome to SaahilCryptoBot Dashboard', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    try:
        if call.data == 'live_prices':
            text = build_portfolio_text()
        elif call.data == 'technical':
            parts = []
            for name, info in portfolio.items():
                closes = get_klines_binance(info['symbol'], limit=60)
                ma14 = calculate_ma(closes, 14)
                rsi = calculate_rsi(closes, 14)
                parts.append(f"{name}: RSI14={rsi if rsi is not None else 'N/A'}, MA14=${ma14 if ma14 is not None else 'N/A'}")
            text = '📊 Technical Analysis\n\n' + '\n'.join(parts)
        elif call.data == 'top_movers':
            text = '🚀 Top Movers 24h\n\n' + get_top_movers()
        elif call.data == 'signals':
            text = '📢 Trading Signals\n\n' + generate_signals_text()
        elif call.data == 'settings':
            text = '⚙️ Settings:\n- Add/Remove coins (future)\n- Notifications (future)'
        else:
            text = 'Unknown action'
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton('Back', callback_data='live_prices'))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    except Exception as e:
        log(f"Callback handler error: {e}")
        try:
            bot.answer_callback_query(call.id, 'Error processing request')
        except:
            pass

# ---- Periodic signals ----
def send_periodic_signals():
    while True:
        try:
            log('Generating periodic signals...')
            text = '📢 Hourly Trading Signals\n\n' + generate_signals_text()
            bot.send_message(ADMIN_ID, text)
            log('Periodic signals sent to admin')
        except Exception as e:
            log(f'Error sending periodic signals: {e}')
        time.sleep(SIGNAL_INTERVAL_SECONDS)

# Start background thread for periodic signals
t = threading.Thread(target=send_periodic_signals, daemon=True)
t.start()

# ---- Webhook endpoints ----
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
    # simple health and connectivity check
    parts = []
    parts.append('Service OK')
    b = http_get_json('https://api.binance.com/api/v3/ping')
    parts.append(f'Binance ping: {"OK" if b == {} else b}')
    try:
        # quick price checks
        for name, info in portfolio.items():
            p = get_price_binance(info['symbol'])
            parts.append(f"{name} price: {p if p else 'Error'}")
    except Exception as e:
        parts.append(f'Health error: {e}')
    return '<br>'.join(str(x) for x in parts), 200

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
    port = int(os.environ.get('PORT', 5000))
    log(f'Starting app on port {port}')
    app.run(host='0.0.0.0', port=port)


