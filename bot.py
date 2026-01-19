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
    user = message.from_user
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('🎣 Начать рыбалку')
    btn2 = types.KeyboardButton('📊 Статистика')
    btn3 = types.KeyboardButton('🎒 Инвентарь')
    btn4 = types.KeyboardButton('❓ Помощь')
    markup.add(btn1, btn2, btn3, btn4)
    
    welcome = f"🎣 Привет, {user.first_name}!\nДобро пожаловать в рыбалку!\n🐛 Червяков: 10/10\n♻️ Пополнение: каждые 15 мин"
    bot.send_message(message.chat.id, welcome, reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == '🎣 Начать рыбалку')
def fishing_handler(message):
    bot.send_message(message.chat.id, "🎣 Рыбалка началась! Жди 5 секунд...")
    
    def finish():
        time.sleep(5)
        fish = random.choice(["🐟 Пескарь", "🐠 Форель", "👑 Золотая рыбка"])
        bot.send_message(message.chat.id, f"🎉 Поймал: {fish}!")
    
    threading.Thread(target=finish).start()

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def run_bot():
    print("🎣 Бот запущен с кнопками!")
    bot.polling(none_stop=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    time.sleep(2)
    run_bot()
