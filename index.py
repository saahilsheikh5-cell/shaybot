import os
from flask import Flask, request
import telebot
from telebot import types
import requests

# --- Bot Token ---
BOT_TOKEN = "7638935379:AAEmLD7JHLZ36Ywh5tvmlP1F8xzrcNrym_Q"
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

# --- Portfolio Data ---
portfolio_data = {
    "Bitcoin": {"amount": 0.5, "symbol": "bitcoin"},
    "Ethereum": {"amount": 2, "symbol": "ethereum"},
    "Solana": {"amount": 50, "symbol": "solana"}
}

# --- Robust price fetch ---
def get_price(symbol):
    try:
        url = f"https://api.coingecko.com/api/v3/simple/price?ids={symbol}&vs_currencies=usd"
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        if symbol in data and "usd" in data[symbol]:
            return data[symbol]["usd"]
        return None
    except Exception as e:
        print(f"Price fetch error for {symbol}: {e}")
        return None

# --- Build portfolio text ---
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

# --- /start command ---
@bot.message_handler(commands=['start'])
def start_command(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("Check Price", callback_data="check_price"))
    markup.add(types.InlineKeyboardButton("Portfolio", callback_data="portfolio"))
    bot.send_message(message.chat.id, "Welcome to SaahilCryptoBot! Choose an option:", reply_markup=markup)

# --- Callback query handler ---
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    # Check price menu
    if call.data == "check_price":
        markup = types.InlineKeyboardMarkup()
        for coin in portfolio_data.keys():
            markup.add(types.InlineKeyboardButton(coin, callback_data=f"price_{coin}"))
        bot.edit_message_text("Select a coin to check price:", call.message.chat.id, call.message.message_id, reply_markup=markup)

    # Individual coin price
    elif call.data.startswith("price_"):
        coin = call.data.split("_")[1]
        price = get_price(portfolio_data[coin]['symbol'])
        if price:
            text = f"The current price of {coin} is ${price:.2f}"
        else:
            text = f"Error fetching price for {coin}"
        # Include a back button
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Back to Coins", callback_data="check_price"))
        markup.add(types.InlineKeyboardButton("Back to Dashboard", callback_data="portfolio"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    # Portfolio dashboard
    elif call.data == "portfolio":
        text = build_portfolio_text()
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Refresh Portfolio", callback_data="portfolio"))
        markup.add(types.InlineKeyboardButton("Check Coin Price", callback_data="check_price"))
        markup.add(types.InlineKeyboardButton("Total Portfolio Value", callback_data="portfolio_value"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

    # Show only total value
    elif call.data == "portfolio_value":
        total = sum((get_price(data['symbol']) or 0) * data['amount'] for data in portfolio_data.values())
        text = f"💰 Total Portfolio Value: ${total:.2f}"
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("Back to Dashboard", callback_data="portfolio"))
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# --- Webhook endpoint ---
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook_handler():
    try:
        update = telebot.types.Update.de_json(request.get_json())
        bot.process_new_updates([update])
    except Exception as e:
        print("Webhook error:", e)
    return "!", 200

# --- Set webhook ---
@app.route('/')
def set_webhook():
    WEBHOOK_URL = "https://shaybot-6.onrender.com/" + BOT_TOKEN
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    return "Webhook set!", 200

# --- Run Flask app ---
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
