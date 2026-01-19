#!/usr/bin/env python3
import os
import telebot
from telebot import types
import json
import time
import random
import re
import threading
from datetime import datetime
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "🎣 Fishing Bot is running!", 200

@app.route('/health')
def health():
    return "OK", 200

BOT_TOKEN = os.environ.get('BOT_TOKEN', '8377535372:AAGLMfn_0P_tDvpJnfv_NmW4QclM2AIojEA')
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# Настройки игры
INITIAL_WORMS = 10
MAX_WORMS = 10
FISHING_TIME = 30
WORM_REFILL_TIME = 900
WARNING_EXPIRE_TIME = 86400
BAN_DURATION = 172800

# Список рыб
FISHES = [
    {"name": "🐟 Пескарь", "rarity": "обычная", "weight": "100-300г", "emoji": "🐟"},
    {"name": "🐟 Окунь", "rarity": "обычная", "weight": "200-500г", "emoji": "🐟"},
    {"name": "🐟 Карась", "rarity": "обычная", "weight": "300-700г", "emoji": "🐟"},
    {"name": "🐟 Плотва", "rarity": "обычная", "weight": "150-400г", "emoji": "🐟"},
    {"name": "🐟 Щука", "rarity": "редкая", "weight": "1-5кг", "emoji": "🐟"},
    {"name": "🐟 Карп", "rarity": "редкая", "weight": "2-8кг", "emoji": "🐟"},
    {"name": "🐠 Форель", "rarity": "редкая", "weight": "1-3кг", "emoji": "🐠"},
    {"name": "🐠 Судак", "rarity": "редкая", "weight": "2-6кг", "emoji": "🐠"},
    {"name": "🐠 Сом", "rarity": "эпическая", "weight": "5-20кг", "emoji": "🐠"},
    {"name": "🎣 Ботинок", "rarity": "мусор", "weight": "1-2кг", "emoji": "🎣"},
    {"name": "👑 Золотая рыбка", "rarity": "легендарная", "weight": "100г", "emoji": "👑"},
]

RARITY_PROBABILITIES = {
    "обычная": 50, "редкая": 30, "эпическая": 15, 
    "легендарная": 4, "мусор": 1
}

class UserDatabase:
    def __init__(self, filename='users.json'):
        self.filename = filename
        self.users = {}
        self.active_fishing = {}
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                'worms': INITIAL_WORMS,
                'fish_caught': [],
                'total_fish': 0,
                'last_fishing_time': None,
                'last_worm_refill': time.time(),
                'stats': {'common': 0, 'rare': 0, 'epic': 0, 'legendary': 0, 'trash': 0},
                'warnings': [],
                'banned_until': None
            }
        return self.users[user_id]

db = UserDatabase()

def calculate_catch():
    total_prob = sum(RARITY_PROBABILITIES.values())
    rand_num = random.randint(1, total_prob)
    current_prob = 0
    
    for rarity, prob in RARITY_PROBABILITIES.items():
        current_prob += prob
        if rand_num <= current_prob:
            selected_rarity = rarity
            break
    
    available_fish = [f for f in FISHES if f['rarity'] == selected_rarity]
    if not available_fish:
        available_fish = [f for f in FISHES if f['rarity'] == "обычная"]
    
    return random.choice(available_fish)

def create_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add('🎣 Начать рыбалку', '📊 Статистика', '🎒 Инвентарь', '❓ Помощь')
    return markup

def create_fishing_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add('🎣 Забросить удочку', '📋 Меню')
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    welcome_text = (
        f"🎣 Привет, {user.first_name}!\n"
        f"Добро пожаловать в мир рыбалки!\n\n"
        f"🐛 Червяков: {user_data['worms']}/10\n"
        f"🐟 Всего поймано: {user_data['total_fish']}\n\n"
        f"♻️ Червяки пополняются каждые 15 минут!\n\n"
        f"Используй кнопки ниже!\n\n"
        f"При желании можете отблагодарить: 2200702034105283"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "🎣 *Помощь по игре \"Рыбалка\"*\n\n"
        "📋 *Основные команды:*\n"
        "/start - Начать игру\n"
        "/fishing - Начать рыбалку\n"
        "/stats - Статистика\n"
        "/inventory - Инвентарь\n"
        "/help - Эта справка\n\n"
        "🎮 *Как играть:*\n"
        "1️⃣ У вас есть червяки 🐛 (макс. 10)\n"
        "2️⃣ Каждая рыбалка тратит 1 червяка\n"
        "3️⃣ Червяки восстанавливаются (1 каждые 15 минут)\n"
        "4️⃣ Рыбалка длится 30 секунд\n\n"
        "⚖️ *Правила:*\n"
        "• Запрещены ссылки (кроме @username)\n"
        "• 1 ссылка = предупреждение\n"
        "• 2 ссылки за 24 часа = бан на 2 дня\n\n"
        "Удачи на рыбалке! 🎣"
    )
    
    bot.send_message(message.chat.id, help_text, reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '🎣 Начать рыбалку')
def fishing_handler(message):
    user = message.from_user
    user_id = str(user.id)
    user_data = db.get_user(user.id)
    
    if user_id in db.active_fishing:
        bot.send_message(message.chat.id, "⏳ Вы уже рыбачите! Подождите...", reply_markup=create_fishing_keyboard())
        return
    
    if user_data['worms'] <= 0:
        bot.send_message(message.chat.id, "😔 Червяки закончились! Жди 15 минут.", reply_markup=create_main_keyboard())
        return
    
    user_data['worms'] -= 1
    msg = bot.send_message(message.chat.id, "🎣 Началась рыбалка! Жди 30 секунд...", reply_markup=create_fishing_keyboard())
    
    def fishing_timer():
        time.sleep(FISHING_TIME)
        
        if user_id in db.active_fishing:
            del db.active_fishing[user_id]
        
        caught_fish = calculate_catch()
        user_data['fish_caught'].append(caught_fish)
        user_data['total_fish'] += 1
        
        result_text = (
            f"🎉 *Рыбалка завершена!*\n\n"
            f"{caught_fish['emoji']} *Поймано:* {caught_fish['name']}\n"
            f"📊 *Редкость:* {caught_fish['rarity']}\n"
            f"⚖️ *Вес:* {caught_fish['weight']}\n\n"
            f"🐛 Червяков осталось: {user_data['worms']}\n"
            f"🐟 Всего поймано: {user_data['total_fish']}"
        )
        
        if caught_fish['rarity'] == 'легендарная':
            result_text += "\n\n🎊 *ВАУ! Легендарная рыба!* 🎊"
        
        bot.send_message(message.chat.id, result_text, reply_markup=create_main_keyboard())
    
    db.active_fishing[user_id] = threading.Thread(target=fishing_timer)
    db.active_fishing[user_id].daemon = True
    db.active_fishing[user_id].start()

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def run_bot():
    print("🎣 Бот запущен на Render!")
    bot.polling(none_stop=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    time.sleep(2)
    run_bot()
