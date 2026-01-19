#!/usr/bin/env python3
import os
import telebot
from telebot import types
import time
import random
import threading
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "🎣 Fishing Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

BOT_TOKEN = os.environ.get('BOT_TOKEN', '8377535372:AAGLMfn_0P_tDvpJnfv_NmW4QclM2AIojEA')
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start_command(message):
    bot.send_message(message.chat.id, "🎣 Бот работает на Render! Напиши /help")

@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id, "Помощь: /start - начать")

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def run_bot():
    print("🎣 Бот запущен!")
    bot.polling(none_stop=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    time.sleep(2)
    run_bot()
