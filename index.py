import os
from flask import Flask, request
import telebot
from telebot import types
import requests

# --- Bot Token ---
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Portfolio Data (customize with your coins and amounts) ---
portfolio_data = {
    "Bitcoin": {"amount": 0.5, "symbol": "bitcoin"},
    "Ethereum": {"amount": 2, "symbol": "ethereum"},
    "Solana": {"amount": 50, "symbol": "solana"}
}

# --- Helper Functions ---
def get_price(symbol):
    try:
        response = requests.get(f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd")
        return response.json()[symbol]["usd"]
    except:
        return None

def build_portfolio_text():
    text = "📊 Your Portfolio:\n\n"
    total_value = 0
    for coin, data in portfolio_data.items():
        price = get_price(data['symbol'])
        if price:
            value = price * data['amount']
            total_value += value
            text += f"{coin}: {data['amount']} × ${price:.2f} = ${value:.2f}\n"
        else:
            text += f"{coin}: Error fetching price\n"
    text += f"\n💰 Total Portfolio Value: ${total_value:.2f}"
    return text

# --- /start Command ---
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Check Price", callback_data="check_price"))
    markup.add(types.InlineKeyboardButton("Portfolio", callback_data="portfolio"))
    bot.send_message(message.chat.id, "Welcome to SaahilCryptoBot! Choose an option:", reply_markup=markup)

# --- Callback Query Handler for Inline Buttons ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "check_price":
        markup = types.InlineKeyboardMarkup()
        for coin in portfolio_data.keys():
            markup.add(types.InlineKeyboardButton(coin, callback_data=f"price_{coin}"))
        bot.edit_message_text("Select a coin to check price:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    elif call.data.startswith("price_"):
        coin = call.data.split("_")[1]
        price = get_price(portfolio_data[coin]['symbol'])
        if price:
            bot.edit_message_text(f"The current price of {coin} is ${price:.2f}", call.message.chat.id, call.message.message_id)
        else:
            bot.edit_message_text(f"Error fetching price for {coin}", call.message.chat.id, call.message.message_id)

    elif call.data == "portfolio":
        text = build_portfolio_text()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Refresh Portfolio", callback_data="portfolio"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# --- Webhook Endpoint ---
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook_handler():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "!", 200

# --- Set Webhook Endpoint ---
@app.route('/')
def set_webhook():
    WEBHOOK_URL = "https://shaybot.onrender.com/" + BOT_TOKEN  # ✅ Correctly formatted
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    return "Webhook set!", 200

# --- Run Flask App ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))


