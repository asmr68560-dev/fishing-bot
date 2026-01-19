#!/usr/bin/env python3
# fishing_bot.py - Полный бот для рыбалки с системой банов
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
WORM_REFILL_TIME = 900  # 15 минут
WARNING_EXPIRE_TIME = 86400  # 24 часа
BAN_DURATION = 172800  # 2 дня

# Список рыб (30 видов)
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
    {"name": "🦞 Рак", "rarity": "обычная", "weight": "50-150г", "emoji": "🦞"},
    {"name": "🐡 Игла-рыба", "rarity": "редкая", "weight": "500г-1кг", "emoji": "🐡"},
    {"name": "🎣 Ботинок", "rarity": "мусор", "weight": "1-2кг", "emoji": "🎣"},
    {"name": "🗑️ Пакет", "rarity": "мусор", "weight": "200г", "emoji": "🗑️"},
    {"name": "🍺 Банка", "rarity": "мусор", "weight": "500г", "emoji": "🍺"},
    {"name": "👑 Золотая рыбка", "rarity": "легендарная", "weight": "100г", "emoji": "👑"},
    {"name": "🐠 Осётр", "rarity": "эпическая", "weight": "10-30кг", "emoji": "🐠"},
    {"name": "🐳 Белуга", "rarity": "легендарная", "weight": "50-100кг", "emoji": "🐳"},
    {"name": "🦈 Акула", "rarity": "легендарная", "weight": "100-200кг", "emoji": "🦈"},
    {"name": "🐙 Кальмар", "rarity": "редкая", "weight": "1-3кг", "emoji": "🐙"},
    {"name": "🦐 Креветка", "rarity": "обычная", "weight": "20-50г", "emoji": "🦐"},
    {"name": "🐚 Мидия", "rarity": "обычная", "weight": "50-100г", "emoji": "🐚"},
    {"name": "🎏 Золотая рыбка (декоративная)", "rarity": "эпическая", "weight": "300г", "emoji": "🎏"},
    {"name": "🪼 Медуза", "rarity": "редкая", "weight": "500г-2кг", "emoji": "🪼"},
    {"name": "🐡 Фугу", "rarity": "эпическая", "weight": "1-2кг", "emoji": "🐡"},
    {"name": "🐠 Тунец", "rarity": "редкая", "weight": "3-10кг", "emoji": "🐠"},
    {"name": "🐟 Лещ", "rarity": "обычная", "weight": "1-3кг", "emoji": "🐟"},
    {"name": "🐟 Сазан", "rarity": "редкая", "weight": "3-12кг", "emoji": "🐟"},
    {"name": "🐠 Лосось", "rarity": "эпическая", "weight": "2-8кг", "emoji": "🐠"},
    {"name": "🦀 Краб", "rarity": "редкая", "weight": "300г-1кг", "emoji": "🦀"},
    {"name": "🌿 Водоросли", "rarity": "мусор", "weight": "100-300г", "emoji": "🌿"}
]

# Редкости и их вероятности
RARITY_PROBABILITIES = {
    "обычная": 50,
    "редкая": 30,
    "эпическая": 15,
    "легендарная": 4,
    "мусор": 1
}

# Регулярные выражения для поиска ссылок
URL_PATTERN = re.compile(
    r'(https?://[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9-]+\.(com|ru|net|org|info|io|me|tv|co|us|uk|de|fr|es|it|jp|cn|рф)[^\s]*)|(t\.me/[^\s]+)|(telegram\.me/[^\s]+)|(tg://[^\s]+)'
)
USERNAME_PATTERN = re.compile(r'@[a-zA-Z0-9_]{5,32}')

class UserDatabase:
    def __init__(self):
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
                'username': None,
                'first_name': None,
                'warnings': [],
                'banned_until': None
            }
        
        # Автопополнение червяков
        user = self.users[user_id]
        current_time = time.time()
        time_passed = current_time - user.get('last_worm_refill', current_time)
        worms_to_add = int(time_passed // WORM_REFILL_TIME)
        
        if worms_to_add > 0:
            user['worms'] = min(user['worms'] + worms_to_add, MAX_WORMS)
            user['last_worm_refill'] = current_time
        
        # Очистка старых предупреждений
        user['warnings'] = [w for w in user['warnings'] if current_time - w < WARNING_EXPIRE_TIME]
        
        return user
    
    def use_worm(self, user_id):
        user = self.get_user(user_id)
        if user['worms'] > 0:
            user['worms'] -= 1
            return True, user['worms']
        return False, user['worms']
    
    def add_fish(self, user_id, fish):
        user = self.get_user(user_id)
        
        catch = {
            'fish': fish['name'],
            'rarity': fish['rarity'],
            'weight': fish['weight'],
            'emoji': fish['emoji'],
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        user['fish_caught'].append(catch)
        if len(user['fish_caught']) > 20:
            user['fish_caught'] = user['fish_caught'][-20:]
        
        user['total_fish'] += 1
        
        # Статистика
        if fish['rarity'] == "обычная":
            user['stats']['common'] += 1
        elif fish['rarity'] == "редкая":
            user['stats']['rare'] += 1
        elif fish['rarity'] == "эпическая":
            user['stats']['epic'] += 1
        elif fish['rarity'] == "легендарная":
            user['stats']['legendary'] += 1
        elif fish['rarity'] == "мусор":
            user['stats']['trash'] += 1
        
        user['last_fishing_time'] = time.time()
        return catch
    
    def add_warning(self, user_id, chat_id=None):
        user = self.get_user(user_id)
        current_time = time.time()
        user['warnings'].append(current_time)
        
        # Проверяем активные предупреждения
        active_warnings = [w for w in user['warnings'] if current_time - w < WARNING_EXPIRE_TIME]
        
        if len(active_warnings) >= 2:
            user['banned_until'] = current_time + BAN_DURATION
            return True, len(active_warnings), True
        
        return False, len(active_warnings), False
    
    def is_banned(self, user_id):
        user = self.get_user(user_id)
        if user.get('banned_until'):
            current_time = time.time()
            if current_time < user['banned_until']:
                return True
            else:
                user['banned_until'] = None
                return False
        return False
    
    def get_ban_time_left(self, user_id):
        user = self.get_user(user_id)
        if user.get('banned_until'):
            current_time = time.time()
            if current_time < user['banned_until']:
                return user['banned_until'] - current_time
        return 0
    
    def get_warning_count(self, user_id):
        user = self.get_user(user_id)
        current_time = time.time()
        active_warnings = [w for w in user['warnings'] if current_time - w < WARNING_EXPIRE_TIME]
        return len(active_warnings)

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
    btn1 = types.KeyboardButton('🎣 Начать рыбалку')
    btn2 = types.KeyboardButton('📊 Статистика')
    btn3 = types.KeyboardButton('🎒 Инвентарь')
    btn4 = types.KeyboardButton('❓ Помощь')
    markup.add(btn1, btn2, btn3, btn4)
    return markup

def create_fishing_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('🎣 Забросить удочку')
    btn2 = types.KeyboardButton('📋 Меню')
    markup.add(btn1, btn2)
    return markup

def ban_user_in_group(chat_id, user_id, user_name):
    try:
        # Пытаемся забанить
        bot.ban_chat_member(chat_id, user_id, until_date=int(time.time()) + BAN_DURATION)
        
        # Пытаемся создать ссылку-приглашение
        try:
            chat_invite = bot.create_chat_invite_link(
                chat_id,
                name=f"Возврат для {user_name}",
                expire_date=int(time.time()) + BAN_DURATION + 86400,
                member_limit=1
            )
            invite_link = chat_invite.invite_link
            
            ban_message = (
                f"🚫 {user_name} забанен на 2 дня!\n"
                f"⚠️ Причина: 2 ссылки за 24 часа\n"
                f"🔗 Ссылка для возврата:\n{invite_link}\n"
                f"📝 Ссылка действует 3 дня"
            )
        except:
            ban_message = (
                f"🚫 {user_name} забанен на 2 дня!\n"
                f"⚠️ Причина: 2 ссылки за 24 часа"
            )
        
        bot.send_message(chat_id, ban_message)
        return True
    except Exception as e:
        print(f"Ошибка бана: {e}")
        # Если не удалось забанить (нет прав), просто отправляем сообщение
        try:
            ban_message = f"🚫 {user_name} получил бан на 2 дня! Причина: 2 ссылки за 24 часа"
            bot.send_message(chat_id, ban_message)
        except:
            pass
        return False

def delete_links_in_group(message):
    if message.chat.type in ['group', 'supergroup']:
        text = message.text or message.caption or ""
        
        if URL_PATTERN.search(text):
            all_matches = URL_PATTERN.findall(text)
            has_other_links = False
            
            for match_group in all_matches:
                for match in match_group:
                    if match and not USERNAME_PATTERN.fullmatch(match):
                        has_other_links = True
                        break
                if has_other_links:
                    break
            
            if has_other_links:
                try:
                    user = message.from_user
                    user_id = str(user.id)
                    chat_id = message.chat.id
                    
                    # Проверяем бан
                    if db.is_banned(user_id):
                        ban_time_left = db.get_ban_time_left(user_id)
                        days_left = int(ban_time_left // 86400)
                        hours_left = int((ban_time_left % 86400) // 3600)
                        minutes_left = int((ban_time_left % 3600) // 60)
                        
                        ban_message = (
                            f"🚫 {user.first_name}, ты уже забанен!\n"
                            f"⏳ Бан истечет через: {days_left}д {hours_left}ч {minutes_left}мин\n"
                            f"📝 Причина: отправка ссылок"
                        )
                        bot.send_message(chat_id, ban_message)
                        return True
                    
                    # Удаляем сообщение
                    bot.delete_message(chat_id, message.message_id)
                    
                    # Добавляем предупреждение
                    banned, warning_count, is_ban = db.add_warning(user_id, chat_id)
                    
                    if is_ban:
                        # Бан на 2 дня
                        ban_user_in_group(chat_id, user.id, user.first_name)
                    else:
                        # Только предупреждение
                        warning_message = (
                            f"⚠️ {user.first_name}, даю предупреждение!\n"
                            f"На 2 раз даю бан, не кидай ссылки\n"
                            f"📊 Предупреждений: {warning_count}/2\n"
                            f"⏳ Предупреждение снимется через 24 часа"
                        )
                        bot.send_message(chat_id, warning_message)
                    
                except Exception as e:
                    print(f"Ошибка удаления ссылки: {e}")
                return True
    return False

@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    if db.is_banned(str(user.id)):
        ban_time_left = db.get_ban_time_left(user.id)
        days_left = int(ban_time_left // 86400)
        hours_left = int((ban_time_left % 86400) // 3600)
        minutes_left = int((ban_time_left % 3600) // 60)
        
        ban_text = (
            f"🚫 {user.first_name}, ты забанен!\n\n"
            f"⏳ Бан истечет через: {days_left}д {hours_left}ч {minutes_left}мин\n"
            f"📝 Причина: отправка ссылок\n\n"
            f"Ожидайте окончания бана для продолжения игры."
        )
        bot.send_message(message.chat.id, ban_text)
        return
    
    welcome_text = (
        f"🎣 Привет, {user.first_name}!\n"
        f"Добро пожаловать в мир рыбалки!\n\n"
        f"🐛 Червяков: {user_data['worms']}/10\n"
        f"🐟 Всего поймано: {user_data['total_fish']}\n\n"
        f"♻️ Червяки теперь пополняются каждые 15 минут!\n\n"
        f"Используй кнопки ниже или команды:\n"
        f"/fishing - Начать рыбалку\n"
        f"/stats - Статистика\n"
        f"/inventory - Инвентарь\n"
        f"/help - Помощь\n\n"
        f"При желании можете отблагодарить: 2200702034105283"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['help'])
def help_command(message):
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    help_text = (
        "🎣 *Помощь по игре \"Рыбалка\"*\n\n"
        "📋 *Основные команды:*\n"
        "/start - Начать игру\n"
        "/fishing - Начать рыбалку\n"
        "/stats - Ваша статистика\n"
        "/inventory - Последние уловы\n"
        "/help - Эта справка\n\n"
        "🎮 *Как играть:*\n"
        "1️⃣ У вас есть червяки 🐛 (макс. 10)\n"
        "2️⃣ Каждая рыбалка тратит 1 червяка\n"
        "3️⃣ Червяки восстанавливаются (1 каждые 15 минут) ♻️\n"
        "4️⃣ Рыбалка длится 30 секунд\n"
        "5️⃣ Можно поймать рыбу разной редкости!\n\n"
        "🐟 *Редкости рыбы:*\n"
        "• 🐟 Обычная (50%)\n"
        "• 🐠 Редкая (30%)\n"
        "• 🌟 Эпическая (15%)\n"
        "• 👑 Легендарная (4%)\n"
        "• 🗑️ Мусор (1%)\n\n"
        "⚖️ *Правила чата (в группах):*\n"
        "• Запрещены любые ссылки (кроме @username)\n"
        "• 1 ссылка = предупреждение\n"
        "• 2 ссылки за 24 часа = бан на 2 дня в группе\n"
        "• @username разрешены\n\n"
        "Удачи на рыбалке! 🎣"
    )
    
    bot.send_message(message.chat.id, help_text, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['stats'])
def stats_command(message):
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    user_data = db.get_user(user.id)
    total = user_data['total_fish']
    
    if total > 0:
        luck_rate = ((user_data['stats']['epic'] + user_data['stats']['legendary']) / total * 100)
        trash_rate = (user_data['stats']['trash'] / total * 100)
    else:
        luck_rate = trash_rate = 0
    
    warning_count = db.get_warning_count(user.id)
    
    stats_text = (
        f"📊 *Статистика {user.first_name}*\n\n"
        f"🐛 Червяков: {user_data['worms']}/10\n"
        f"🎣 Всего попыток: {user_data['total_fish']}\n"
        f"⚠️ Предупреждений: {warning_count}/2\n\n"
        f"🐟 *Поймано:*\n"
        f"• 🐟 Обычных: {user_data['stats']['common']}\n"
        f"• 🐠 Редких: {user_data['stats']['rare']}\n"
        f"• 🌟 Эпических: {user_data['stats']['epic']}\n"
        f"• 👑 Легендарных: {user_data['stats']['legendary']}\n"
        f"• 🗑️ Мусора: {user_data['stats']['trash']}\n\n"
        f"🎯 *Эффективность:*\n"
        f"Удача: {luck_rate:.1f}%\n"
        f"Мусор: {trash_rate:.1f}%"
    )
    
    bot.send_message(message.chat.id, stats_text, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['inventory'])
def inventory_command(message):
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    user_data = db.get_user(user.id)
    
    if not user_data['fish_caught']:
        inventory_text = "🎒 Ваш инвентарь пуст.\nНачните рыбалку, чтобы поймать первую рыбу!"
    else:
        inventory_text = f"🎒 *Последние уловы {user.first_name}:*\n\n"
        for i, catch in enumerate(reversed(user_data['fish_caught'][-10:]), 1):
            inventory_text += f"{i}. {catch['emoji']} {catch['fish']}\n"
            inventory_text += f"   📊 {catch['rarity']}, ⚖️ {catch['weight']}\n\n"
    
    bot.send_message(message.chat.id, inventory_text, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['fishing'])
def fishing_command_handler(message):
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    # Проверяем ссылки в группе
    if delete_links_in_group(message):
        return
    
    user_id = str(user.id)
    
    if user_id in db.active_fishing:
        bot.send_message(message.chat.id, "⏳ Вы уже рыбачите! Подождите...", reply_markup=create_fishing_keyboard())
        return
    
    user_data = db.get_user(user.id)
    
    if user_data['worms'] <= 0:
        current_time = time.time()
        last_refill = user_data.get('last_worm_refill', current_time)
        next_worm_in = WORM_REFILL_TIME - (current_time - last_refill)
        
        if next_worm_in > 0:
            minutes = int(next_worm_in // 60)
            seconds = int(next_worm_in % 60)
            bot.send_message(message.chat.id,
                           f"😔 Червяки закончились!\n"
                           f"Следующий червяк через: {minutes} мин {seconds} сек\n"
                           f"♻️ Червяки пополняются каждые 15 минут.",
                           reply_markup=create_main_keyboard())
        else:
            user_data['worms'] = min(user_data['worms'] + 1, MAX_WORMS)
            user_data['last_worm_refill'] = current_time
            bot.send_message(message.chat.id,
                           f"🎉 Червяки пополнились! Теперь у вас {user_data['worms']} червяков.",
                           reply_markup=create_main_keyboard())
        return
    
    success, worms_left = db.use_worm(user.id)
    
    if not success:
        bot.send_message(message.chat.id, "Ошибка! Не удалось начать рыбалку.")
        return
    
    msg = bot.send_message(message.chat.id,
                          f"🎣 *Началась рыбалка!*\n\n"
                          f"🐛 Потрачен 1 червяк\n"
                          f"🕐 Осталось червяков: {worms_left}\n"
                          f"⏳ Рыбалка продлится {FISHING_TIME} секунд\n\n"
                          f"Ждите... рыба клюёт!",
                          reply_markup=create_fishing_keyboard())
    
    def fishing_timer():
        time.sleep(FISHING_TIME)
        
        if user_id in db.active_fishing:
            del db.active_fishing[user_id]
        
        caught_fish = calculate_catch()
        catch_info = db.add_fish(user.id, caught_fish)
        user_data = db.get_user(user.id)
        
        rarity_emojis = {
            'обычная': '🐟',
            'редкая': '🐠',
            'эпическая': '🌟',
            'легендарная': '👑',
            'мусор': '🗑️'
        }
        
        result_text = (
            f"🎉 *Рыбалка завершена!*\n\n"
            f"{rarity_emojis.get(caught_fish['rarity'], '🎣')} *Поймано:* {caught_fish['name']}\n"
            f"📊 *Редкость:* {caught_fish['rarity']}\n"
            f"⚖️ *Вес:* {caught_fish['weight']}\n\n"
            f"🐛 Червяков осталось: {user_data['worms']}\n"
            f"🐟 Всего поймано: {user_data['total_fish']}\n\n"
        )
        
        if caught_fish['rarity'] == 'легендарная':
            result_text += "🎊 *ВАУ! Легендарная рыба!* 🎊\n"
        elif caught_fish['rarity'] == 'мусор':
            result_text += "😔 Не повезло... Попробуйте еще раз!\n"
        
        try:
            bot.send_message(message.chat.id, result_text, reply_markup=create_main_keyboard())
        except Exception as e:
            print(f"Ошибка отправки: {e}")
    
    db.active_fishing[user_id] = threading.Thread(target=fishing_timer)
    db.active_fishing[user_id].daemon = True
    db.active_fishing[user_id].start()

@bot.message_handler(func=lambda msg: msg.text == '🎣 Начать рыбалку')
def fishing_button_handler(message):
    fishing_command_handler(message)

@bot.message_handler(func=lambda msg: msg.text == '🎣 Забросить удочку')
def fishing_cast_handler(message):
    fishing_command_handler(message)

@bot.message_handler(func=lambda msg: msg.text == '📊 Статистика')
def stats_button_handler(message):
    stats_command(message)

@bot.message_handler(func=lambda msg: msg.text == '🎒 Инвентарь')
def inventory_button_handler(message):
    inventory_command(message)

@bot.message_handler(func=lambda msg: msg.text == '❓ Помощь')
def help_button_handler(message):
    help_command(message)

@bot.message_handler(func=lambda msg: msg.text == '📋 Меню')
def menu_command(message):
    bot.send_message(message.chat.id, "Возвращаю в главное меню:", reply_markup=create_main_keyboard())

# Обработчик всех сообщений для проверки ссылок
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_messages(message):
    delete_links_in_group(message)
    
    text = message.text
    if text in ['🎣 Начать рыбалку', '📊 Статистика', '🎒 Инвентарь', '❓ Помощь', '🎣 Забросить удочку', '📋 Меню']:
        return
    if text and text.startswith('/'):
        return

@bot.message_handler(content_types=['photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle_media_messages(message):
    delete_links_in_group(message)

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port, debug=False)

def run_bot():
    print("🎣 Бот запущен со всеми функциями!")
    print("✅ Игра 'Рыбалка' с 30 видами рыб")
    print("✅ Система банов за ссылки в группах")
    print("✅ Червяки пополняются каждые 15 минут")
    bot.polling(none_stop=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    time.sleep(2)
    run_bot()
