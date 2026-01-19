#!/usr/bin/env python3
# bot.py - Полный бот с админ-панелью и магазином
import os
import telebot
from telebot import types
import json
import time
import random
import re
import threading
import requests
from datetime import datetime, timedelta
from flask import Flask, request
import logging
from collections import defaultdict

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# ========== KEEP-ALIVE SYSTEM ==========
class KeepAliveService:
    """Сервис для поддержания бота в активном состоянии на Render"""
    
    def __init__(self, base_url):
        self.base_url = base_url
        self.running = False
        self.thread = None
        self.ping_interval = 480  # 8 минут (меньше 15 мин сна Render)
        
    def start(self):
        """Запускаем keep-alive в фоновом режиме"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._ping_loop, daemon=True)
        self.thread.start()
        print(f"✅ Keep-alive запущен. Ping каждые {self.ping_interval//60} минут")
        
    def _ping_loop(self):
        """Основной цикл пингов"""
        ping_count = 0
        self._send_ping()
        ping_count += 1
        
        while self.running:
            try:
                time.sleep(self.ping_interval)
                if self.running:
                    self._send_ping()
                    ping_count += 1
            except Exception as e:
                logger.error(f"Ошибка в keep-alive: {e}")
                
    def _send_ping(self):
        """Отправляем ping запрос"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                logger.info("🔄 Ping успешен")
        except Exception as e:
            logger.error(f"❌ Ошибка ping: {e}")

# ========== CONFIGURATION ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8377535372:AAGLMfn_0P_tDvpJnfv_NmW4QclM2AIojEA')
bot = telebot.TeleBot(BOT_TOKEN)

# Получаем URL от Render
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
WEBHOOK_URL = f'{RENDER_URL}/{BOT_TOKEN}' if RENDER_URL else None

# Настройки игры
INITIAL_WORMS = 10
MAX_WORMS = 20  # Увеличили с покупкой улучшений
FISHING_TIME = 30
WORM_REFILL_TIME = 900  # 15 минут
WARNING_EXPIRE_TIME = 86400  # 24 часа
BAN_DURATION = 172800  # 2 дня

# ========== УДОЧКИ ==========
RODS = [
    {"id": "basic", "name": "🎣 Простая удочка", "price": 0, "level": 1, "bonus": "Без бонуса", "emoji": "🎣"},
    {"id": "spinning", "name": "🎣 Спиннинг", "price": 100, "level": 2, "bonus": "+5% к редкой рыбе", "emoji": "🎣"},
    {"id": "feeder", "name": "🎣 Фидерная", "price": 250, "level": 3, "bonus": "+10% к эпической", "emoji": "🎣"},
    {"id": "fly", "name": "🎣 Нахлыстовая", "price": 500, "level": 4, "bonus": "+15% к легендарной", "emoji": "🎣"},
    {"id": "winter", "name": "🎣 Зимняя удочка", "price": 150, "level": 2, "bonus": "Зимой +20% удачи", "emoji": "🎣"},
    {"id": "sea", "name": "🎣 Морская удочка", "price": 300, "level": 3, "bonus": "+2 червяка в инвентаре", "emoji": "🎣"},
    {"id": "carbon", "name": "🎣 Углепластиковая", "price": 400, "level": 4, "bonus": "-5 секунд рыбалки", "emoji": "🎣"},
    {"id": "telescopic", "name": "🎣 Телескопическая", "price": 200, "level": 2, "bonus": "Можно ловить 2 рыбы", "emoji": "🎣"},
    {"id": "bamboo", "name": "🎣 Бамбуковая", "price": 350, "level": 3, "bonus": "Анти-мусор +10%", "emoji": "🎣"},
    {"id": "golden", "name": "🎣 Золотая удочка", "price": 1000, "level": 5, "bonus": "Все бонусы ×2", "emoji": "🎣"},
    {"id": "ice", "name": "🧊 Ледяная удочка", "price": 600, "level": 4, "bonus": "Замораживает время", "emoji": "🧊"},
    {"id": "fire", "name": "🔥 Огненная удочка", "price": 700, "level": 4, "bonus": "Сжигает мусор", "emoji": "🔥"},
    {"id": "electric", "name": "⚡ Электрическая", "price": 800, "level": 4, "bonus": "Шанс на 2 рыбы", "emoji": "⚡"},
    {"id": "invisible", "name": "👻 Невидимая", "price": 900, "level": 5, "bonus": "Рыба не пугается", "emoji": "👻"},
    {"id": "ancient", "name": "🏺 Древняя", "price": 1200, "level": 5, "bonus": "Шанс на артефакт", "emoji": "🏺"},
    {"id": "crystal", "name": "💎 Хрустальная", "price": 1500, "level": 6, "bonus": "×3 монеты за рыбу", "emoji": "💎"},
    {"id": "neon", "name": "💡 Неоновая", "price": 850, "level": 4, "bonus": "Светится в темноте", "emoji": "💡"},
    {"id": "mechanical", "name": "⚙️ Механическая", "price": 950, "level": 5, "bonus": "Автоподсечка", "emoji": "⚙️"},
    {"id": "quantum", "name": "🔮 Квантовая", "price": 2000, "level": 7, "bonus": "Квантовые рыбы", "emoji": "🔮"},
    {"id": "legendary", "name": "👑 Легендарная", "price": 5000, "level": 10, "bonus": "ВСЕ рыбы легендарные", "emoji": "👑"},
]

# ========== РЫБЫ (80 видов) ==========
FISHES = [
    # Старые 30 видов
    {"name": "🐟 Пескарь", "rarity": "обычная", "weight": "100-300г", "price": 5, "emoji": "🐟"},
    {"name": "🐟 Окунь", "rarity": "обычная", "weight": "200-500г", "price": 7, "emoji": "🐟"},
    {"name": "🐟 Карась", "rarity": "обычная", "weight": "300-700г", "price": 8, "emoji": "🐟"},
    {"name": "🐟 Плотва", "rarity": "обычная", "weight": "150-400г", "price": 6, "emoji": "🐟"},
    {"name": "🐟 Щука", "rarity": "редкая", "weight": "1-5кг", "price": 30, "emoji": "🐟"},
    {"name": "🐟 Карп", "rarity": "редкая", "weight": "2-8кг", "price": 35, "emoji": "🐟"},
    {"name": "🐠 Форель", "rarity": "редкая", "weight": "1-3кг", "price": 40, "emoji": "🐠"},
    {"name": "🐠 Судак", "rarity": "редкая", "weight": "2-6кг", "price": 45, "emoji": "🐠"},
    {"name": "🐠 Сом", "rarity": "эпическая", "weight": "5-20кг", "price": 100, "emoji": "🐠"},
    {"name": "🦞 Рак", "rarity": "обычная", "weight": "50-150г", "price": 10, "emoji": "🦞"},
    {"name": "🐡 Игла-рыба", "rarity": "редкая", "weight": "500г-1кг", "price": 25, "emoji": "🐡"},
    {"name": "🎣 Ботинок", "rarity": "мусор", "weight": "1-2кг", "price": 1, "emoji": "🎣"},
    {"name": "🗑️ Пакет", "rarity": "мусор", "weight": "200г", "price": 1, "emoji": "🗑️"},
    {"name": "🍺 Банка", "rarity": "мусор", "weight": "500г", "price": 2, "emoji": "🍺"},
    {"name": "👑 Золотая рыбка", "rarity": "легендарная", "weight": "100г", "price": 500, "emoji": "👑"},
    {"name": "🐠 Осётр", "rarity": "эпическая", "weight": "10-30кг", "price": 150, "emoji": "🐠"},
    {"name": "🐳 Белуга", "rarity": "легендарная", "weight": "50-100кг", "price": 1000, "emoji": "🐳"},
    {"name": "🦈 Акула", "rarity": "легендарная", "weight": "100-200кг", "price": 1200, "emoji": "🦈"},
    {"name": "🐙 Кальмар", "rarity": "редкая", "weight": "1-3кг", "price": 50, "emoji": "🐙"},
    {"name": "🦐 Креветка", "rarity": "обычная", "weight": "20-50г", "price": 3, "emoji": "🦐"},
    {"name": "🐚 Мидия", "rarity": "обычная", "weight": "50-100г", "price": 4, "emoji": "🐚"},
    {"name": "🎏 Золотая рыбка (декоративная)", "rarity": "эпическая", "weight": "300г", "price": 300, "emoji": "🎏"},
    {"name": "🪼 Медуза", "rarity": "редкая", "weight": "500г-2кг", "price": 35, "emoji": "🪼"},
    {"name": "🐡 Фугу", "rarity": "эпическая", "weight": "1-2кг", "price": 200, "emoji": "🐡"},
    {"name": "🐠 Тунец", "rarity": "редкая", "weight": "3-10кг", "price": 60, "emoji": "🐠"},
    {"name": "🐟 Лещ", "rarity": "обычная", "weight": "1-3кг", "price": 15, "emoji": "🐟"},
    {"name": "🐟 Сазан", "rarity": "редкая", "weight": "3-12кг", "price": 55, "emoji": "🐟"},
    {"name": "🐠 Лосось", "rarity": "эпическая", "weight": "2-8кг", "price": 120, "emoji": "🐠"},
    {"name": "🦀 Краб", "rarity": "редкая", "weight": "300г-1кг", "price": 40, "emoji": "🦀"},
    {"name": "🌿 Водоросли", "rarity": "мусор", "weight": "100-300г", "price": 1, "emoji": "🌿"},
    
    # Новые 50 рыб
    {"name": "🐠 Барракуда", "rarity": "редкая", "weight": "3-7кг", "price": 65, "emoji": "🐠"},
    {"name": "🐟 Густера", "rarity": "обычная", "weight": "200-600г", "price": 9, "emoji": "🐟"},
    {"name": "🐡 Скат", "rarity": "эпическая", "weight": "10-50кг", "price": 250, "emoji": "🐡"},
    {"name": "🐟 Язь", "rarity": "редкая", "weight": "1-3кг", "price": 45, "emoji": "🐟"},
    {"name": "🐠 Марлин", "rarity": "легендарная", "weight": "50-150кг", "price": 1500, "emoji": "🐠"},
    {"name": "🦑 Спрут", "rarity": "эпическая", "weight": "5-15кг", "price": 180, "emoji": "🦑"},
    {"name": "🐟 Красноперка", "rarity": "обычная", "weight": "100-400г", "price": 8, "emoji": "🐟"},
    {"name": "🐠 Сельдь", "rarity": "обычная", "weight": "300-800г", "price": 12, "emoji": "🐠"},
    {"name": "🐡 Морской конёк", "rarity": "редкая", "weight": "50-200г", "price": 75, "emoji": "🐡"},
    {"name": "🐟 Линь", "rarity": "редкая", "weight": "1-4кг", "price": 50, "emoji": "🐟"},
    {"name": "🐠 Анчоус", "rarity": "обычная", "weight": "20-100г", "price": 4, "emoji": "🐠"},
    {"name": "🦞 Омар", "rarity": "эпическая", "weight": "1-4кг", "price": 220, "emoji": "🦞"},
    {"name": "🐟 Вьюн", "rarity": "обычная", "weight": "50-150г", "price": 6, "emoji": "🐟"},
    {"name": "🐠 Сардина", "rarity": "обычная", "weight": "100-300г", "price": 7, "emoji": "🐠"},
    {"name": "🐡 Рыба-меч", "rarity": "легендарная", "weight": "100-300кг", "price": 2000, "emoji": "🐡"},
    {"name": "🐟 Угорь", "rarity": "редкая", "weight": "1-5кг", "price": 80, "emoji": "🐟"},
    {"name": "🐠 Скалярия", "rarity": "редкая", "weight": "300г-1кг", "price": 55, "emoji": "🐠"},
    {"name": "🦐 Лангуст", "rarity": "эпическая", "weight": "2-8кг", "price": 280, "emoji": "🦐"},
    {"name": "🐟 Бычок", "rarity": "обычная", "weight": "100-500г", "price": 10, "emoji": "🐟"},
    {"name": "🐠 Стерлядь", "rarity": "эпическая", "weight": "2-6кг", "price": 350, "emoji": "🐠"},
    {"name": "🐡 Рыба-клоун", "rarity": "редкая", "weight": "100-400г", "price": 90, "emoji": "🐡"},
    {"name": "🐟 Хек", "rarity": "обычная", "weight": "500г-2кг", "price": 18, "emoji": "🐟"},
    {"name": "🐠 Севанская форель", "rarity": "эпическая", "weight": "3-10кг", "price": 400, "emoji": "🐠"},
    {"name": "🦀 Королевский краб", "rarity": "легендарная", "weight": "3-10кг", "price": 800, "emoji": "🦀"},
    {"name": "🐟 Треска", "rarity": "редкая", "weight": "2-10кг", "price": 70, "emoji": "🐟"},
    {"name": "🐠 Дорадо", "rarity": "редкая", "weight": "1-5кг", "price": 85, "emoji": "🐠"},
    {"name": "🐡 Мандаринка", "rarity": "редкая", "weight": "50-200г", "price": 95, "emoji": "🐡"},
    {"name": "🐟 Налим", "rarity": "редкая", "weight": "1-6кг", "price": 65, "emoji": "🐟"},
    {"name": "🐠 Барабулька", "rarity": "обычная", "weight": "100-400г", "price": 14, "emoji": "🐠"},
    {"name": "🦞 Речной рак", "rarity": "обычная", "weight": "80-200г", "price": 11, "emoji": "🦞"},
    {"name": "🐟 Горбуша", "rarity": "редкая", "weight": "1-3кг", "price": 60, "emoji": "🐟"},
    {"name": "🐠 Кефаль", "rarity": "обычная", "weight": "500г-2кг", "price": 20, "emoji": "🐠"},
    {"name": "🐡 Рыба-лев", "rarity": "эпическая", "weight": "500г-1кг", "price": 320, "emoji": "🐡"},
    {"name": "🐟 Зубатка", "rarity": "редкая", "weight": "3-15кг", "price": 110, "emoji": "🐟"},
    {"name": "🐠 Сайра", "rarity": "обычная", "weight": "200-600г", "price": 16, "emoji": "🐠"},
    {"name": "🦐 Тигровая креветка", "rarity": "редкая", "weight": "50-150г", "price": 45, "emoji": "🦐"},
    {"name": "🐟 Минтай", "rarity": "обычная", "weight": "500г-3кг", "price": 13, "emoji": "🐟"},
    {"name": "🐠 Камбала", "rarity": "редкая", "weight": "1-7кг", "price": 75, "emoji": "🐠"},
    {"name": "🐡 Рыба-шарик", "rarity": "редкая", "weight": "200-800г", "price": 100, "emoji": "🐡"},
    {"name": "🐟 Скумбрия", "rarity": "обычная", "weight": "300г-1кг", "price": 17, "emoji": "🐟"},
    {"name": "🐠 Хариус", "rarity": "эпическая", "weight": "1-3кг", "price": 380, "emoji": "🐠"},
    {"name": "🦀 Мангровый краб", "rarity": "редкая", "weight": "200-800г", "price": 65, "emoji": "🦀"},
    {"name": "🐟 Корюшка", "rarity": "обычная", "weight": "50-150г", "price": 9, "emoji": "🐟"},
    {"name": "🐠 Сибас", "rarity": "эпическая", "weight": "2-8кг", "price": 420, "emoji": "🐠"},
    {"name": "🐡 Рыба-попугай", "rarity": "редкая", "weight": "300г-1кг", "price": 115, "emoji": "🐡"},
    {"name": "🐟 Омуль", "rarity": "эпическая", "weight": "1-3кг", "price": 450, "emoji": "🐟"},
    {"name": "🐠 Нерка", "rarity": "редкая", "weight": "2-7кг", "price": 130, "emoji": "🐠"},
    {"name": "🦞 Гигантский омар", "rarity": "легендарная", "weight": "5-20кг", "price": 1200, "emoji": "🦞"},
    {"name": "🐟 Сайка", "rarity": "обычная", "weight": "100-300г", "price": 11, "emoji": "🐟"},
    {"name": "🐠 Белый амур", "rarity": "эпическая", "weight": "5-30кг", "price": 500, "emoji": "🐠"},
    {"name": "🐡 Рыба-луна", "rarity": "легендарная", "weight": "100-1000кг", "price": 3000, "emoji": "🐡"},
]

# Улучшенный мусор (10 видов)
TRASH_UPGRADES = [
    {"name": "🔧 Запчасти от удочки", "rarity": "улучшение", "effect": "Ремонт удочки +10%", "price": 50, "emoji": "🔧"},
    {"name": "💎 Драгоценный камень", "rarity": "улучшение", "effect": "+100 монет", "price": 100, "emoji": "💎"},
    {"name": "🗝️ Ключ от сундука", "rarity": "улучшение", "effect": "Открывает случайный сундук", "price": 150, "emoji": "🗝️"},
    {"name": "🧪 Эликсир удачи", "rarity": "улучшение", "effect": "+5% к легендарной", "price": 200, "emoji": "🧪"},
    {"name": "⚡ Батарейка", "rarity": "улучшение", "effect": "Ускоряет рыбалку", "price": 75, "emoji": "⚡"},
    {"name": "🔮 Магический кристалл", "rarity": "улучшение", "effect": "Показывает рыбу заранее", "price": 300, "emoji": "🔮"},
    {"name": "🧭 Компас", "rarity": "улучшение", "effect": "Находит лучшие места", "price": 125, "emoji": "🧭"},
    {"name": "🛡️ Защитный амулет", "rarity": "улучшение", "effect": "Защищает от мусора", "price": 175, "emoji": "🛡️"},
    {"name": "📜 Карта сокровищ", "rarity": "улучшение", "effect": "Ведет к кладу", "price": 250, "emoji": "📜"},
    {"name": "👁️ Всевидящее око", "rarity": "улучшение", "effect": "Видит все рыбы в воде", "price": 500, "emoji": "👁️"},
]

# Редкости и их вероятности
RARITY_PROBABILITIES = {
    "обычная": 45,
    "редкая": 30,
    "эпическая": 15,
    "легендарная": 4,
    "мусор": 5,
    "улучшение": 1  # Новый тип - улучшение из мусора
}

# Регулярные выражения
URL_PATTERN = re.compile(
    r'(https?://[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9-]+\.(com|ru|net|org|info|io|me|tv|co|us|uk|de|fr|es|it|jp|cn|рф)[^\s]*)|(t\.me/[^\s]+)|(telegram\.me/[^\s]+)|(tg://[^\s]+)'
)

# ========== USER DATABASE ==========
class UserDatabase:
    def __init__(self):
        self.users = {}
        self.active_fishing = {}
        self.admins = {}
        self.logs = []
        self.load_data()
    
    def load_data(self):
        """Загружаем данные из файлов"""
        try:
            with open('users_data.json', 'r', encoding='utf-8') as f:
                self.users = json.load(f)
            print(f"✅ Загружено {len(self.users)} пользователей")
        except FileNotFoundError:
            print("📁 Файл данных не найден, начинаем с чистого листа")
            self.users = {}
        except Exception as e:
            print(f"⚠️ Ошибка загрузки данных: {e}")
            self.users = {}
        
        # Загружаем админов
        try:
            with open('admins_data.json', 'r', encoding='utf-8') as f:
                self.admins = json.load(f)
            print(f"✅ Загружено {len(self.admins)} админов")
        except:
            self.admins = {}
            # Добавляем владельца как админа 5 уровня
            self.admins['5330661807'] = {
                'level': 5,
                'username': 'Владелец',
                'added_by': 'system',
                'added_time': datetime.now().isoformat()
            }
        
        # Загружаем логи
        try:
            with open('logs_data.json', 'r', encoding='utf-8') as f:
                self.logs = json.load(f)
        except:
            self.logs = []
    
    def save_data(self):
        """Сохраняем данные в файлы"""
        try:
            with open('users_data.json', 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
        
        try:
            with open('admins_data.json', 'w', encoding='utf-8') as f:
                json.dump(self.admins, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения админов: {e}")
        
        try:
            with open('logs_data.json', 'w', encoding='utf-8') as f:
                json.dump(self.logs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения логов: {e}")
    
    def add_log(self, action, admin_id, target_id=None, details=""):
        """Добавляем запись в логи"""
        log_entry = {
            'time': datetime.now().isoformat(),
            'action': action,
            'admin_id': str(admin_id),
            'target_id': str(target_id) if target_id else None,
            'details': details
        }
        self.logs.append(log_entry)
        if len(self.logs) > 1000:  # Ограничиваем логи
            self.logs = self.logs[-1000:]
        self.save_data()
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                'worms': INITIAL_WORMS,
                'fish_caught': [],
                'total_fish': 0,
                'coins': 100,  # Начальные монеты
                'rods': ['basic'],  # Начальная удочка
                'active_rod': 'basic',
                'upgrades': [],
                'last_fishing_time': None,
                'last_worm_refill': time.time(),
                'last_daily_bonus': 0,
                'stats': {'common': 0, 'rare': 0, 'epic': 0, 'legendary': 0, 'trash': 0, 'upgrades': 0},
                'username': None,
                'first_name': None,
                'warnings': [],
                'banned_until': None,
                'level': 1,
                'experience': 0
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
    
    def is_admin(self, user_id, min_level=1):
        """Проверяем, является ли пользователь админом"""
        return str(user_id) in self.admins and self.admins[str(user_id)]['level'] >= min_level
    
    def add_admin(self, user_id, level, added_by, username=""):
        """Добавляем админа"""
        user_id = str(user_id)
        self.admins[user_id] = {
            'level': level,
            'username': username,
            'added_by': str(added_by),
            'added_time': datetime.now().isoformat()
        }
        self.add_log('add_admin', added_by, user_id, f'Уровень: {level}')
        self.save_data()
        return True
    
    def remove_admin(self, user_id, removed_by):
        """Удаляем админа"""
        user_id = str(user_id)
        if user_id in self.admins:
            del self.admins[user_id]
            self.add_log('remove_admin', removed_by, user_id)
            self.save_data()
            return True
        return False
    
    def change_admin_level(self, user_id, new_level, changed_by):
        """Изменяем уровень админа"""
        user_id = str(user_id)
        if user_id in self.admins:
            old_level = self.admins[user_id]['level']
            self.admins[user_id]['level'] = new_level
            self.add_log('change_admin_level', changed_by, user_id, f'{old_level} -> {new_level}')
            self.save_data()
            return True
        return False
    
    def use_worm(self, user_id):
        user = self.get_user(user_id)
        if user['worms'] > 0:
            user['worms'] -= 1
            self.save_data()
            return True, user['worms']
        return False, user['worms']
    
    def add_fish(self, user_id, fish):
        user = self.get_user(user_id)
        
        catch = {
            'fish': fish['name'],
            'rarity': fish['rarity'],
            'weight': fish['weight'],
            'price': fish.get('price', 0),
            'emoji': fish['emoji'],
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        user['fish_caught'].append(catch)
        if len(user['fish_caught']) > 50:  # Увеличили до 50
            user['fish_caught'] = user['fish_caught'][-50:]
        
        user['total_fish'] += 1
        
        # Добавляем монеты за рыбу
        if fish['rarity'] != "мусор" and fish['rarity'] != "улучшение":
            user['coins'] += fish.get('price', 0)
        
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
        elif fish['rarity'] == "улучшение":
            user['stats']['upgrades'] += 1
            # Применяем улучшение
            self.apply_upgrade(user_id, fish)
        
        # Добавляем опыт
        experience_gained = {
            "обычная": 1,
            "редкая": 3,
            "эпическая": 10,
            "легендарная": 50,
            "мусор": 0,
            "улучшение": 5
        }.get(fish['rarity'], 0)
        
        user['experience'] += experience_gained
        old_level = user['level']
        user['level'] = user['experience'] // 100 + 1
        
        if user['level'] > old_level:
            user['worms'] = min(user['worms'] + 2, MAX_WORMS)  # Бонус за уровень
        
        user['last_fishing_time'] = time.time()
        self.save_data()
        return catch
    
    def apply_upgrade(self, user_id, upgrade_item):
        """Применяем улучшение из мусора"""
        user = self.get_user(user_id)
        if upgrade_item['name'] not in [u['name'] for u in user['upgrades']]:
            user['upgrades'].append({
                'name': upgrade_item['name'],
                'effect': upgrade_item['effect'],
                'time': datetime.now().isoformat()
            })
            user['coins'] += upgrade_item.get('price', 0)
    
    def add_warning(self, user_id, chat_id=None):
        user = self.get_user(user_id)
        current_time = time.time()
        user['warnings'].append(current_time)
        
        # Проверяем активные предупреждения
        active_warnings = [w for w in user['warnings'] if current_time - w < WARNING_EXPIRE_TIME]
        
        if len(active_warnings) >= 2:
            user['banned_until'] = current_time + BAN_DURATION
            self.save_data()
            return True, len(active_warnings), True
        
        self.save_data()
        return False, len(active_warnings), False
    
    def is_banned(self, user_id):
        user = self.get_user(user_id)
        if user.get('banned_until'):
            current_time = time.time()
            if current_time < user['banned_until']:
                return True
            else:
                user['banned_until'] = None
                self.save_data()
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
    
    def ban_user(self, user_id, days, reason, admin_id):
        """Бан пользователя админом"""
        user = self.get_user(user_id)
        user['banned_until'] = time.time() + (days * 86400)
        self.add_log('ban', admin_id, user_id, f'{days} дней. Причина: {reason}')
        self.save_data()
        return True
    
    def unban_user(self, user_id, admin_id):
        """Разбан пользователя админом"""
        user = self.get_user(user_id)
        user['banned_until'] = None
        user['warnings'] = []
        self.add_log('unban', admin_id, user_id)
        self.save_data()
        return True
    
    def get_top_users(self, limit=10, by='coins'):
        """Топ игроков"""
        if by == 'coins':
            key_func = lambda x: x[1]['coins']
        elif by == 'level':
            key_func = lambda x: x[1]['level']
        else:  # total_fish
            key_func = lambda x: x[1]['total_fish']
        
        sorted_users = sorted(
            self.users.items(),
            key=key_func,
            reverse=True
        )
        return sorted_users[:limit]
    
    def add_coins(self, user_id, amount, admin_id=None):
        """Добавить монеты (админ или система)"""
        user = self.get_user(user_id)
        user['coins'] += amount
        if admin_id:
            self.add_log('add_coins', admin_id, user_id, f'{amount} монет')
        self.save_data()
        return user['coins']
    
    def add_rod(self, user_id, rod_id, admin_id=None):
        """Добавить удочку"""
        user = self.get_user(user_id)
        if rod_id not in user['rods']:
            user['rods'].append(rod_id)
            if admin_id:
                self.add_log('add_rod', admin_id, user_id, rod_id)
            self.save_data()
            return True
        return False
    
    def buy_rod(self, user_id, rod_id):
        """Покупка удочки в магазине"""
        user = self.get_user(user_id)
        rod = next((r for r in RODS if r['id'] == rod_id), None)
        
        if not rod:
            return False, "Удочка не найдена"
        
        if rod_id in user['rods']:
            return False, "У вас уже есть эта удочка"
        
        if user['coins'] < rod['price']:
            return False, "Недостаточно монет"
        
        user['coins'] -= rod['price']
        user['rods'].append(rod_id)
        self.save_data()
        return True, "Удочка куплена!"
    
    def sell_fish(self, user_id, fish_index=None):
        """Продажа рыбы"""
        user = self.get_user(user_id)
        
        if not user['fish_caught']:
            return False, "Нет рыбы для продажи"
        
        if fish_index is None:  # Продать все
            total_price = sum(f.get('price', 0) for f in user['fish_caught'] if f.get('price', 0) > 0)
            user['coins'] += total_price
            user['fish_caught'] = []
            self.save_data()
            return True, f"Вся рыба продана за {total_price} монет!"
        else:  # Продать конкретную
            try:
                fish = user['fish_caught'][fish_index]
                price = fish.get('price', 0)
                if price <= 0:
                    return False, "Эту рыбу нельзя продать"
                
                user['coins'] += price
                user['fish_caught'].pop(fish_index)
                self.save_data()
                return True, f"Рыба продана за {price} монет!"
            except IndexError:
                return False, "Рыба не найдена"
    
    def get_daily_bonus(self, user_id):
        """Ежедневный бонус"""
        user = self.get_user(user_id)
        current_time = time.time()
        last_bonus = user.get('last_daily_bonus', 0)
        
        if current_time - last_bonus >= 86400:  # 24 часа
            # Бонус зависит от уровня
            bonus_coins = user['level'] * 10 + 50
            bonus_worms = min(user['level'] // 3 + 1, 5)
            
            user['coins'] += bonus_coins
            user['worms'] = min(user['worms'] + bonus_worms, MAX_WORMS)
            user['last_daily_bonus'] = current_time
            self.save_data()
            
            return {
                'success': True,
                'coins': bonus_coins,
                'worms': bonus_worms,
                'total_coins': user['coins'],
                'total_worms': user['worms']
            }
        else:
            next_in = 86400 - (current_time - last_bonus)
            hours = int(next_in // 3600)
            minutes = int((next_in % 3600) // 60)
            return {
                'success': False,
                'time_left': f"{hours}ч {minutes}мин"
            }

db = UserDatabase()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def calculate_catch(user_id=None):
    """Расчет улова с учетом удочки"""
    total_prob = sum(RARITY_PROBABILITIES.values())
    rand_num = random.randint(1, total_prob)
    current_prob = 0
    
    # Бонусы от удочки
    bonus_multiplier = 1.0
    if user_id:
        user = db.get_user(user_id)
        active_rod = next((r for r in RODS if r['id'] == user.get('active_rod', 'basic')), RODS[0])
        # Здесь можно добавить логику бонусов от удочки
    
    selected_rarity = "обычная"
    for rarity, prob in RARITY_PROBABILITIES.items():
        current_prob += prob
        if rand_num <= current_prob:
            selected_rarity = rarity
            break
    
    if selected_rarity == "улучшение":
        return random.choice(TRASH_UPGRADES)
    
    available_fish = [f for f in FISHES if f['rarity'] == selected_rarity]
    if not available_fish:
        available_fish = [f for f in FISHES if f['rarity'] == "обычная"]
    
    return random.choice(available_fish)

def create_main_keyboard(user_id=None):
    """Создание основной клавиатуры"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Основные кнопки
    btn1 = types.KeyboardButton('🎣 Начать рыбалку')
    btn2 = types.KeyboardButton('📊 Статистика')
    btn3 = types.KeyboardButton('🎒 Инвентарь')
    btn4 = types.KeyboardButton('🏪 Магазин')
    
    # Дополнительные кнопки
    btn5 = types.KeyboardButton('🎁 Ежедневный бонус')
    btn6 = types.KeyboardButton('🏆 Топ игроков')
    btn7 = types.KeyboardButton('❓ Помощь')
    
    # Кнопка админа (только для админов)
    if user_id and db.is_admin(user_id, 1):
        btn8 = types.KeyboardButton('👑 Админ-панель')
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8)
    else:
        markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7)
    
    return markup

def create_fishing_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('🎣 Забросить удочку')
    btn2 = types.KeyboardButton('📋 Меню')
    markup.add(btn1, btn2)
    return markup

def create_admin_keyboard(admin_level):
    """Клавиатура для админ-панели"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    if admin_level >= 1:
        markup.add(
            types.InlineKeyboardButton('🚫 Бан пользователя', callback_data='admin_ban'),
            types.InlineKeyboardButton('✅ Снять бан', callback_data='admin_unban')
        )
    
    if admin_level >= 2:
        markup.add(
            types.InlineKeyboardButton('📋 Логи банов', callback_data='admin_ban_logs'),
            types.InlineKeyboardButton('👥 Логи админов', callback_data='admin_admin_logs')
        )
    
    if admin_level >= 3:
        markup.add(
            types.InlineKeyboardButton('💰 Выдать монеты', callback_data='admin_add_coins'),
            types.InlineKeyboardButton('🎣 Выдать удочку', callback_data='admin_add_rod')
        )
    
    if admin_level >= 4:
        markup.add(
            types.InlineKeyboardButton('📊 Статистика игрока', callback_data='admin_user_stats'),
            types.InlineKeyboardButton('🔍 Поиск игрока', callback_data='admin_find_user')
        )
    
    if admin_level >= 5:
        markup.add(
            types.InlineKeyboardButton('👑 Назначить админа', callback_data='admin_add_admin'),
            types.InlineKeyboardButton('📉 Изменить уровень', callback_data='admin_change_level'),
            types.InlineKeyboardButton('🗑️ Очистить логи', callback_data='admin_clear_logs'),
            types.InlineKeyboardButton('💣 Сбросить статистику', callback_data='admin_reset_stats')
        )
    
    markup.add(types.InlineKeyboardButton('❌ Закрыть', callback_data='admin_close'))
    return markup

def create_shop_keyboard():
    """Клавиатура для магазина"""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton('🎣 Удочки', callback_data='shop_rods'),
        types.InlineKeyboardButton('🐟 Продать рыбу', callback_data='shop_sell_fish'),
        types.InlineKeyboardButton('⚡ Улучшения', callback_data='shop_upgrades'),
        types.InlineKeyboardButton('💼 Мой инвентарь', callback_data='shop_inventory'),
        types.InlineKeyboardButton('❌ Закрыть', callback_data='shop_close')
    )
    return markup

def ban_user_in_group(chat_id, user_id, user_name):
    try:
        bot.ban_chat_member(chat_id, user_id, until_date=int(time.time()) + BAN_DURATION)
        ban_message = f"🚫 {user_name} забанен на 2 дня!\n⚠️ Причина: 2 ссылки за 24 часа"
        bot.send_message(chat_id, ban_message)
        return True
    except Exception as e:
        logger.error(f"Ошибка бана: {e}")
        return False

def delete_links_in_group(message):
    if message.chat.type in ['group', 'supergroup']:
        text = message.text or message.caption or ""
        
        if URL_PATTERN.search(text):
            try:
                user = message.from_user
                user_id = str(user.id)
                chat_id = message.chat.id
                
                if db.is_banned(user_id):
                    bot.delete_message(chat_id, message.message_id)
                    return True
                
                bot.delete_message(chat_id, message.message_id)
                banned, warning_count, is_ban = db.add_warning(user_id, chat_id)
                
                if is_ban:
                    ban_user_in_group(chat_id, user.id, user.first_name)
                else:
                    warning_message = f"⚠️ {user.first_name}, предупреждение {warning_count}/2"
                    bot.send_message(chat_id, warning_message)
                
                return True
            except Exception as e:
                logger.error(f"Ошибка удаления ссылки: {e}")
    return False

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    if db.is_banned(str(user.id)):
        ban_time_left = db.get_ban_time_left(user.id)
        days_left = int(ban_time_left // 86400)
        hours_left = int((ban_time_left % 86400) // 3600)
        minutes_left = int((ban_time_left % 3600) // 60)
        
        ban_text = f"🚫 {user.first_name}, ты забанен!\n⏳ Бан истечет через: {days_left}д {hours_left}ч {minutes_left}мин"
        bot.send_message(message.chat.id, ban_text)
        return
    
    welcome_text = (
        f"🎣 Привет, {user.first_name}!\n"
        f"Добро пожаловать в мир рыбалки!\n\n"
        f"🐛 Червяков: {user_data['worms']}/{MAX_WORMS}\n"
        f"💰 Монет: {user_data['coins']}\n"
        f"🎣 Удочка: {next((r['name'] for r in RODS if r['id'] == user_data.get('active_rod', 'basic')), 'Базовая')}\n"
        f"📈 Уровень: {user_data['level']}\n\n"
        f"Используй кнопки ниже для игры!\n\n"
        f"Если хотите поддержать: 2200702034105283"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_keyboard(user.id))

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "🎣 *Помощь по игре \"Рыбалка\"*\n\n"
        "📋 *Основные команды:*\n"
        "/start - Начать игру\n"
        "/fishing - Начать рыбалку\n"
        "/stats - Ваша статистика\n"
        "/inventory - Последние уловы\n"
        "/shop - Магазин\n"
        "/top - Топ игроков\n"
        "/daily - Ежедневный бонус\n"
        "/help - Эта справка\n\n"
        "🎮 *Как играть:*\n"
        "1️⃣ У вас есть червяки 🐛 (макс. 20)\n"
        "2️⃣ Каждая рыбалка тратит 1 червяка\n"
        "3️⃣ Червяки восстанавливаются каждые 15 минут\n"
        "4️⃣ Рыбалка длится 30 секунд\n"
        "5️⃣ Можно поймать 80 видов рыб!\n\n"
        "🏪 *Магазин:*\n"
        "• Покупайте новые удочки (20 видов)\n"
        "• Продавайте рыбу за монеты\n"
        "• Покупайте улучшения\n\n"
        "Удачи на рыбалке! 🎣"
    )
    
    bot.send_message(message.chat.id, help_text, reply_markup=create_main_keyboard(message.from_user.id))

@bot.message_handler(commands=['stats'])
def stats_command(message):
    user = message.from_user
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
        f"🐛 Червяков: {user_data['worms']}/{MAX_WORMS}\n"
        f"💰 Монет: {user_data['coins']}\n"
        f"📈 Уровень: {user_data['level']} (Опыт: {user_data['experience']}/100)\n"
        f"🎣 Удочек: {len(user_data['rods'])}\n\n"
        f"🎣 Всего попыток: {user_data['total_fish']}\n"
        f"⚠️ Предупреждений: {warning_count}/2\n\n"
        f"🐟 *Поймано:*\n"
        f"• 🐟 Обычных: {user_data['stats']['common']}\n"
        f"• 🐠 Редких: {user_data['stats']['rare']}\n"
        f"• 🌟 Эпических: {user_data['stats']['epic']}\n"
        f"• 👑 Легендарных: {user_data['stats']['legendary']}\n"
        f"• 🗑️ Мусора: {user_data['stats']['trash']}\n"
        f"• ⚡ Улучшений: {user_data['stats']['upgrades']}\n\n"
        f"🎯 Удача: {luck_rate:.1f}% | Мусор: {trash_rate:.1f}%"
    )
    
    bot.send_message(message.chat.id, stats_text, reply_markup=create_main_keyboard(user.id))

@bot.message_handler(commands=['inventory'])
def inventory_command(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    # Инвентарь рыбы
    if not user_data['fish_caught']:
        fish_text = "🎒 Рыбы в инвентаре нет."
    else:
        fish_text = f"🎒 *Последние уловы ({len(user_data['fish_caught'])}):*\n\n"
        for i, catch in enumerate(reversed(user_data['fish_caught'][-10:]), 1):
            fish_text += f"{i}. {catch['emoji']} {catch['fish']}\n"
            fish_text += f"   📊 {catch['rarity']}, ⚖️ {catch['weight']}, 💰 {catch.get('price', 0)} монет\n\n"
    
    # Инвентарь удочек
    rods_text = "\n🎣 *Ваши удочки:*\n"
    for rod_id in user_data['rods']:
        rod = next((r for r in RODS if r['id'] == rod_id), None)
        if rod:
            active = " ✅" if user_data.get('active_rod') == rod_id else ""
            rods_text += f"• {rod['emoji']} {rod['name']}{active}\n"
    
    # Улучшения
    upgrades_text = "\n⚡ *Ваши улучшения:*\n"
    if user_data['upgrades']:
        for upgrade in user_data['upgrades'][-5:]:
            upgrades_text += f"• {upgrade.get('emoji', '⚡')} {upgrade['name']}\n"
    else:
        upgrades_text += "Нет улучшений\n"
    
    bot.send_message(message.chat.id, fish_text + rods_text + upgrades_text, reply_markup=create_main_keyboard(user.id))

@bot.message_handler(commands=['shop'])
def shop_command(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    shop_text = (
        f"🏪 *Магазин рыбалки*\n\n"
        f"💰 Ваш баланс: {user_data['coins']} монет\n\n"
        f"Выберите раздел:"
    )
    
    bot.send_message(message.chat.id, shop_text, reply_markup=create_shop_keyboard())

@bot.message_handler(commands=['top'])
def top_command(message):
    top_users = db.get_top_users(10, 'coins')
    
    text = "🏆 *Топ 10 рыбаков по монетам:*\n\n"
    for i, (user_id, user_data) in enumerate(top_users, 1):
        name = user_data.get('first_name', f'ID{user_id[:6]}')
        text += f"{i}. {name} - {user_data['coins']}💰 (Ур.{user_data['level']})\n"
    
    bot.send_message(message.chat.id, text, reply_markup=create_main_keyboard(message.from_user.id))

@bot.message_handler(commands=['daily'])
def daily_command(message):
    result = db.get_daily_bonus(message.from_user.id)
    
    if result['success']:
        text = (
            f"🎁 *Ежедневный бонус!*\n\n"
            f"💰 +{result['coins']} монет\n"
            f"🐛 +{result['worms']} червяков\n\n"
            f"💼 Теперь у вас:\n"
            f"💰 {result['total_coins']} монет\n"
            f"🐛 {result['total_worms']}/{MAX_WORMS} червяков\n\n"
            f"Следующий бонус через 24 часа!"
        )
    else:
        text = f"⏳ Бонус будет доступен через:\n{result['time_left']}"
    
    bot.send_message(message.chat.id, text, reply_markup=create_main_keyboard(message.from_user.id))

@bot.message_handler(commands=['admin'])
def admin_command(message):
    user = message.from_user
    
    if not db.is_admin(user.id, 1):
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к админ-панели!")
        return
    
    admin_info = db.admins.get(str(user.id), {})
    admin_level = admin_info.get('level', 1)
    
    admin_text = (
        f"👑 *Админ-панель*\n\n"
        f"🆔 Ваш ID: {user.id}\n"
        f"📊 Уровень: {admin_level}\n"
        f"👤 Имя: {user.first_name}\n\n"
        f"Выберите действие:"
    )
    
    bot.send_message(message.chat.id, admin_text, reply_markup=create_admin_keyboard(admin_level))

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['бан', 'ban'])
def admin_ban_command(message):
    user = message.from_user
    
    if not db.is_admin(user.id, 1):
        return
    
    try:
        # Формат: /ban @username 7 причина
        parts = message.text.split()
        if len(parts) < 3:
            bot.send_message(message.chat.id, "❌ Формат: /ban @username дни причина")
            return
        
        username = parts[1].replace('@', '')
        days = int(parts[2])
        reason = ' '.join(parts[3:]) if len(parts) > 3 else "Не указана"
        
        # Здесь нужно найти ID пользователя по username
        # Пока заглушка
        target_id = None
        
        if target_id:
            db.ban_user(target_id, days, reason, user.id)
            bot.send_message(message.chat.id, f"✅ Пользователь @{username} забанен на {days} дней")
        else:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['разбан', 'unban'])
def admin_unban_command(message):
    user = message.from_user
    
    if not db.is_admin(user.id, 1):
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ Формат: /unban @username")
            return
        
        username = parts[1].replace('@', '')
        # Поиск ID по username
        target_id = None
        
        if target_id:
            db.unban_user(target_id, user.id)
            bot.send_message(message.chat.id, f"✅ Пользователь @{username} разбанен")
        else:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['монеты', 'coins'])
def admin_coins_command(message):
    user = message.from_user
    
    if not db.is_admin(user.id, 3):
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.send_message(message.chat.id, "❌ Формат: /coins @username количество")
            return
        
        username = parts[1].replace('@', '')
        amount = int(parts[2])
        # Поиск ID по username
        target_id = None
        
        if target_id:
            new_balance = db.add_coins(target_id, amount, user.id)
            bot.send_message(message.chat.id, f"✅ @{username} выдано {amount} монет\n💰 Новый баланс: {new_balance}")
        else:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['+админ', 'addadmin'])
def admin_add_admin_command(message):
    user = message.from_user
    
    if not db.is_admin(user.id, 5):
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 3:
            bot.send_message(message.chat.id, "❌ Формат: /+админ @username уровень")
            return
        
        username = parts[1].replace('@', '')
        level = int(parts[2])
        
        if level < 1 or level > 5:
            bot.send_message(message.chat.id, "❌ Уровень должен быть от 1 до 5")
            return
        
        # Поиск ID по username
        target_id = None
        
        if target_id:
            db.add_admin(target_id, level, user.id, username)
            bot.send_message(message.chat.id, f"✅ @{username} назначен админом {level} уровня")
        else:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

@bot.message_handler(commands=['-админ', 'removeadmin'])
def admin_remove_admin_command(message):
    user = message.from_user
    
    if not db.is_admin(user.id, 5):
        return
    
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.send_message(message.chat.id, "❌ Формат: /-админ @username")
            return
        
        username = parts[1].replace('@', '')
        # Поиск ID по username
        target_id = None
        
        if target_id:
            if db.remove_admin(target_id, user.id):
                bot.send_message(message.chat.id, f"✅ @{username} удален из админов")
            else:
                bot.send_message(message.chat.id, "❌ Пользователь не является админом")
        else:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {e}")

# ========== РЫБАЛКА ==========
@bot.message_handler(commands=['fishing'])
def fishing_command_handler(message):
    user = message.from_user
    
    if db.is_banned(str(user.id)):
        return
    
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
                           f"😔 Червяки закончились!\nСледующий червяк через: {minutes:02d}:{seconds:02d}",
                           reply_markup=create_main_keyboard(user.id))
        else:
            user_data['worms'] = min(user_data['worms'] + 1, MAX_WORMS)
            user_data['last_worm_refill'] = current_time
            db.save_data()
            bot.send_message(message.chat.id,
                           f"🎉 Червяки пополнились! Теперь у вас {user_data['worms']} червяков.",
                           reply_markup=create_main_keyboard(user.id))
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
        
        caught_fish = calculate_catch(user.id)
        catch_info = db.add_fish(user.id, caught_fish)
        user_data = db.get_user(user.id)
        
        rarity_emojis = {
            'обычная': '🐟',
            'редкая': '🐠',
            'эпическая': '🌟',
            'легендарная': '👑',
            'мусор': '🗑️',
            'улучшение': '⚡'
        }
        
        result_text = (
            f"🎉 *Рыбалка завершена!*\n\n"
            f"{rarity_emojis.get(caught_fish['rarity'], '🎣')} *Поймано:* {caught_fish['name']}\n"
            f"📊 *Редкость:* {caught_fish['rarity']}\n"
            f"⚖️ *Вес:* {caught_fish['weight']}\n"
        )
        
        if caught_fish['rarity'] in ['обычная', 'редкая', 'эпическая', 'легендарная']:
            result_text += f"💰 *Цена:* {caught_fish.get('price', 0)} монет\n"
        
        if caught_fish['rarity'] == 'улучшение':
            result_text += f"✨ *Эффект:* {caught_fish['effect']}\n"
            result_text += f"💰 *Бонус:* +{caught_fish.get('price', 0)} монет\n"
        
        result_text += f"\n🐛 Червяков осталось: {user_data['worms']}\n"
        result_text += f"💰 Монет: {user_data['coins']}\n"
        result_text += f"🎣 Всего поймано: {user_data['total_fish']}\n\n"
        
        if caught_fish['rarity'] == 'легендарная':
            result_text += "🎊 *ВАУ! Легендарная рыба!* 🎊\n"
        elif caught_fish['rarity'] == 'улучшение':
            result_text += "🎯 *Отличная находка!* 🎯\n"
        elif caught_fish['rarity'] == 'мусор':
            result_text += "😔 Не повезло... Попробуйте еще раз!\n"
        
        try:
            bot.send_message(message.chat.id, result_text, reply_markup=create_main_keyboard(user.id))
        except Exception as e:
            logger.error(f"Ошибка отправки: {e}")

    db.active_fishing[user_id] = threading.Thread(target=fishing_timer)
    db.active_fishing[user_id].daemon = True
    db.active_fishing[user_id].start()

# ========== ОБРАБОТЧИКИ КНОПОК ==========
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

@bot.message_handler(func=lambda msg: msg.text == '🏪 Магазин')
def shop_button_handler(message):
    shop_command(message)

@bot.message_handler(func=lambda msg: msg.text == '🎁 Ежедневный бонус')
def daily_button_handler(message):
    daily_command(message)

@bot.message_handler(func=lambda msg: msg.text == '🏆 Топ игроков')
def top_button_handler(message):
    top_command(message)

@bot.message_handler(func=lambda msg: msg.text == '❓ Помощь')
def help_button_handler(message):
    help_command(message)

@bot.message_handler(func=lambda msg: msg.text == '👑 Админ-панель')
def admin_button_handler(message):
    admin_command(message)

@bot.message_handler(func=lambda msg: msg.text == '📋 Меню')
def menu_command(message):
    bot.send_message(message.chat.id, "Возвращаю в главное меню:", reply_markup=create_main_keyboard(message.from_user.id))

# ========== CALLBACK ОБРАБОТЧИКИ ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    
    if call.data == 'shop_close':
        bot.delete_message(call.message.chat.id, call.message.message_id)
    
    elif call.data == 'shop_rods':
        user_data = db.get_user(user_id)
        text = "🎣 *Удочки в магазине:*\n\n"
        
        for rod in RODS:
            owned = " ✅" if rod['id'] in user_data['rods'] else ""
            affordable = " 💰" if user_data['coins'] >= rod['price'] else " 🔴"
            text += f"{rod['emoji']} *{rod['name']}*\n"
            text += f"💰 Цена: {rod['price']} монет{affordable}\n"
            text += f"📊 Уровень: {rod['level']} | ✨ {rod['bonus']}{owned}\n"
            if rod['id'] not in user_data['rods'] and user_data['coins'] >= rod['price']:
                text += f"   /buy_{rod['id']}\n"
            text += "\n"
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=create_shop_keyboard(),
            parse_mode='Markdown'
        )
    
    elif call.data == 'shop_sell_fish':
        user_data = db.get_user(user_id)
        if not user_data['fish_caught']:
            text = "🎣 У вас нет рыбы для продажи."
        else:
            total_value = sum(f.get('price', 0) for f in user_data['fish_caught'] if f.get('price', 0) > 0)
            text = f"💰 *Продажа рыбы*\n\nВсего рыбы: {len(user_data['fish_caught'])}\nОбщая стоимость: {total_value} монет\n\n/sell_all - продать всю рыбу\n/sell_номер - продать конкретную рыбу"
        
        bot.edit_message_text(
            text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=create_shop_keyboard()
        )
    
    elif call.data.startswith('admin_'):
        if not db.is_admin(user_id, 1):
            bot.answer_callback_query(call.id, "⛔ Нет доступа!")
            return
        
        admin_info = db.admins.get(str(user_id), {})
        admin_level = admin_info.get('level', 1)
        
        if call.data == 'admin_close':
            bot.delete_message(call.message.chat.id, call.message.message_id)
        
        elif call.data == 'admin_ban':
            if admin_level >= 1:
                bot.send_message(call.message.chat.id, "Введите команду:\n/ban @username дни причина")
            else:
                bot.answer_callback_query(call.id, "⛔ Недостаточно прав!")
        
        elif call.data == 'admin_unban':
            if admin_level >= 1:
                bot.send_message(call.message.chat.id, "Введите команду:\n/unban @username")
            else:
                bot.answer_callback_query(call.id, "⛔ Недостаточно прав!")
        
        elif call.data == 'admin_ban_logs':
            if admin_level >= 2:
                ban_logs = [log for log in db.logs if log['action'] in ['ban', 'unban']][-10:]
                text = "📋 *Последние 10 действий с банами:*\n\n"
                for log in ban_logs:
                    text += f"⏰ {log['time'][:19]}\n"
                    text += f"👤 Админ: {log['admin_id']}\n"
                    text += f"🎯 Действие: {log['action']}\n"
                    if log['target_id']:
                        text += f"👥 Цель: {log['target_id']}\n"
                    if log['details']:
                        text += f"📝 Детали: {log['details']}\n"
                    text += "\n"
                bot.send_message(call.message.chat.id, text)
            else:
                bot.answer_callback_query(call.id, "⛔ Недостаточно прав!")
        
        elif call.data == 'admin_admin_logs':
            if admin_level >= 2:
                admin_logs = [log for log in db.logs if 'admin' in log['action']][-10:]
                text = "👑 *Последние 10 действий с админами:*\n\n"
                for log in admin_logs:
                    text += f"⏰ {log['time'][:19]}\n"
                    text += f"👤 Админ: {log['admin_id']}\n"
                    text += f"🎯 Действие: {log['action']}\n"
                    if log['details']:
                        text += f"📝 Детали: {log['details']}\n"
                    text += "\n"
                bot.send_message(call.message.chat.id, text)
            else:
                bot.answer_callback_query(call.id, "⛔ Недостаточно прав!")

# ========== ПРОДАЖА РЫБЫ КОМАНДЫ ==========
@bot.message_handler(commands=['sell_all'])
def sell_all_command(message):
    success, result = db.sell_fish(message.from_user.id)
    bot.send_message(message.chat.id, result, reply_markup=create_main_keyboard(message.from_user.id))

@bot.message_handler(commands=['buy_'])
def buy_rod_command(message):
    try:
        rod_id = message.text.split('_')[1]
        success, result = db.buy_rod(message.from_user.id, rod_id)
        bot.send_message(message.chat.id, result, reply_markup=create_main_keyboard(message.from_user.id))
    except:
        bot.send_message(message.chat.id, "❌ Ошибка покупки")

# ========== ОБРАБОТКА ВСЕХ СООБЩЕНИЙ ==========
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_messages(message):
    delete_links_in_group(message)
    
    text = message.text
    if text in ['🎣 Начать рыбалку', '📊 Статистика', '🎒 Инвентарь', '🏪 Магазин', 
                '🎁 Ежедневный бонус', '🏆 Топ игроков', '❓ Помощь', '👑 Админ-панель',
                '🎣 Забросить удочку', '📋 Меню']:
        return
    if text and text.startswith('/'):
        return

@bot.message_handler(content_types=['photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle_media_messages(message):
    delete_links_in_group(message)

# ========== WEBHOOK РОУТЫ ==========
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'ok', 200
    return 'error', 403

@app.route('/')
def home():
    return "🎣 Fishing Bot с админ-панелью и магазином работает!", 200

@app.route('/set_webhook')
def set_webhook_route():
    if not WEBHOOK_URL:
        return "❌ RENDER_EXTERNAL_URL не настроен", 500
    
    try:
        bot.remove_webhook()
        time.sleep(0.1)
        s = bot.set_webhook(
            url=WEBHOOK_URL,
            max_connections=50,
            allowed_updates=["message", "callback_query"]
        )
        
        if s:
            return f"✅ Webhook установлен!\nURL: {WEBHOOK_URL}", 200
        else:
            return "❌ Ошибка установки webhook", 500
    except Exception as e:
        return f"❌ Ошибка: {str(e)}", 500

@app.route('/health')
def health():
    return "OK", 200

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
if __name__ == '__main__':
    print("=" * 50)
    print("🎣 Fishing Bot с админ-панелью и магазином")
    print(f"✅ Webhook URL: {WEBHOOK_URL if WEBHOOK_URL else 'Не настроен'}")
    print("=" * 50)
    
    try:
        bot_info = bot.get_me()
        print(f"✅ Бот загружен: @{bot_info.username}")
    except Exception as e:
        print(f"❌ Ошибка загрузки бота: {e}")
    
    # Запускаем keep-alive
    if RENDER_URL:
        keeper = KeepAliveService(RENDER_URL)
        keeper.start()
        print("✅ Keep-alive service started")
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Запуск Flask на порту {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
