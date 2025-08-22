import telebot
from telebot import types
from flask import Flask, request
import requests

BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
WEBHOOK_URL = "https://shaybot-11.onrender.com/" + BOT_TOKEN
ADMIN_ID = 1263295916

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Price Fetcher ---
def get_price(symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}USDT"
        data = requests.get(url, timeout=5).json()
        return float(data["price"])
    except Exception as e:
        return None

# --- Dashboard ---
@bot.message_handler(commands=['start'])
def start(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📈 Check Prices", "📊 Portfolio")
    markup.add("📢 Signals", "🚀 Top Movers")
    markup.add("⚙️ Settings")
    bot.send_message(message.chat.id, "Welcome to Saahil Crypto Bot 🚀", reply_markup=markup)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.text == "📈 Check Prices":
        btc = get_price("BTC") or "Error"
        eth = get_price("ETH") or "Error"
        sol = get_price("SOL") or "Error"
        bot.send_message(message.chat.id, f"BTC: {btc}
ETH: {eth}
SOL: {sol}")

    elif message.text == "📊 Portfolio":
        btc = get_price("BTC") or 0
        eth = get_price("ETH") or 0
        sol = get_price("SOL") or 0
        total = (btc if btc else 0) + (eth if eth else 0) + (sol if sol else 0)
        bot.send_message(message.chat.id, f"Your Portfolio:
BTC={btc}
ETH={eth}
SOL={sol}
💰 Total={total}")

    elif message.text == "📢 Signals":
        bot.send_message(message.chat.id, "Signals feature coming soon 📡")

    elif message.text == "🚀 Top Movers":
        bot.send_message(message.chat.id, "Top movers feature coming soon 🚀")

    elif message.text == "⚙️ Settings":
        bot.send_message(message.chat.id, "Settings coming soon ⚙️")

# --- Webhook Routes ---
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates([telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    return "Webhook set", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)


