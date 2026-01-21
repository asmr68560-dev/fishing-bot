#!/usr/bin/env python3
# bot_fish_extended.py - Расширенный бот для рыбалки с донатом и админкой
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
import hashlib

app = Flask(__name__)

# ========== KEEP-ALIVE SYSTEM ==========
class KeepAliveService:
    """Сервис для поддержания бота в активном состоянии на Render"""
    
    def __init__(self, base_url):
        self.base_url = base_url
        self.running = False
        self.thread = None
        self.ping_interval = 480  # 8 минут
        
    def start(self):
        """Запускаем keep-alive в фоновом режиме"""
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._ping_loop, daemon=True)
        self.thread.start()
        print(f"✅ Keep-alive запущен. Ping каждые {self.ping_interval//60} минут")
        
    def stop(self):
        """Останавливаем keep-alive"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            
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
                    
                    if ping_count % 10 == 0:
                        print(f"📊 Keep-alive: отправлено {ping_count} пингов")
                        
            except Exception as e:
                print(f"⚠️ Ошибка в keep-alive: {e}")
                
    def _send_ping(self):
        """Отправляем ping запрос"""
        try:
            start_time = time.time()
            response = requests.get(
                f"{self.base_url}/health",
                timeout=10,
                headers={'User-Agent': 'KeepAlive/1.0'}
            )
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                print(f"🔄 Ping успешен: {response.text.strip()} ({elapsed:.1f} сек)")
            else:
                print(f"⚠️ Ping ошибка: {response.status_code}")
                
        except requests.exceptions.Timeout:
            print("⏰ Ping timeout (10 сек)")
        except requests.exceptions.ConnectionError:
            print("🔌 Ошибка соединения")
        except Exception as e:
            print(f"❌ Ошибка ping: {type(e).__name__}")

# ========== CONFIGURATION ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8377535372:AAGLMfn_0P_tDvpJnfv_NmW4QclM2AIojEA')
bot = telebot.TeleBot(BOT_TOKEN)

RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
WEBHOOK_URL = f'{RENDER_URL}/{BOT_TOKEN}' if RENDER_URL else None

# ========== НОВЫЕ КОНСТАНТЫ ==========
INITIAL_BASIC_WORMS = 10
MAX_BASIC_WORMS = 10
FISHING_TIME = 30
WORM_REFILL_TIME = 900
WARNING_EXPIRE_TIME = 86400
BAN_DURATION = 172800

# Админы (5 лвл - полные права, 1 лвл - только донат)
ADMINS = {
    '5330661807': 5,  # Полные права
    '8351629145': 5,  # Полные права
    '7093049365': 5   # Полные права (тоже 5 лвл как указано)
}

# ID для пересылки чеков (все 5 лвл)
CHECK_ADMINS = ['8351629145', '7093049365']

# ========== БАЗЫ ДАННЫХ ==========
# 1. Водоемы (10 реальных мест в России)
WATER_BODIES = [
    {
        "id": 1,
        "name": "Онежское озеро",
        "region": "Карелия",
        "emoji": "🌊",
        "depth": "средняя",
        "fish": [1, 2, 3, 4, 5, 6, 10, 11, 16, 17, 19, 20, 22, 25, 26, 27, 28, 29]
    },
    {
        "id": 2,
        "name": "Ладожское озеро",
        "region": "Ленинградская обл.",
        "emoji": "🏞️",
        "depth": "глубокое",
        "fish": [1, 2, 3, 5, 6, 7, 8, 9, 16, 17, 19, 20, 25, 27, 28, 29, 30]
    },
    {
        "id": 3,
        "name": "Волга",
        "region": "Центральная Россия",
        "emoji": "🌉",
        "depth": "разная",
        "fish": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 16, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
    },
    {
        "id": 4,
        "name": "Енисей",
        "region": "Сибирь",
        "emoji": "❄️",
        "depth": "глубокое",
        "fish": [1, 2, 3, 5, 6, 7, 8, 9, 16, 17, 19, 25, 27, 28, 30]
    },
    {
        "id": 5,
        "name": "Байкал",
        "region": "Иркутская обл.",
        "emoji": "💎",
        "depth": "очень глубокое",
        "fish": [7, 8, 16, 19, 20, 22, 25, 28, 29, 30]
    },
    {
        "id": 6,
        "name": "Амур",
        "region": "Дальний Восток",
        "emoji": "🐉",
        "depth": "разная",
        "fish": [1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30]
    },
    {
        "id": 7,
        "name": "Дон",
        "region": "Юг России",
        "emoji": "🌅",
        "depth": "мелкое",
        "fish": [1, 2, 3, 4, 5, 6, 10, 11, 19, 20, 21, 22, 26, 27, 29]
    },
    {
        "id": 8,
        "name": "Кубань",
        "region": "Краснодарский край",
        "emoji": "☀️",
        "depth": "разная",
        "fish": [1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 19, 20, 21, 22, 25, 26, 27, 29]
    },
    {
        "id": 9,
        "name": "Обь",
        "region": "Западная Сибирь",
        "emoji": "🌲",
        "depth": "разная",
        "fish": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 16, 19, 20, 21, 25, 26, 27, 28, 29, 30]
    },
    {
        "id": 10,
        "name": "Кама",
        "region": "Приволжье",
        "emoji": "⛰️",
        "depth": "разная",
        "fish": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 19, 20, 21, 22, 25, 26, 27, 28, 29]
    }
]

# 2. Наживки (5 видов)
BAITS = [
    {"id": 1, "name": "Белый опарыш", "emoji": "⚪", "price": 5, "effectiveness": "высокая", "fish_preference": [1, 2, 3, 4, 10, 26]},
    {"id": 2, "name": "Красный опарыш", "emoji": "🔴", "price": 7, "effectiveness": "очень высокая", "fish_preference": [5, 6, 7, 8, 25, 27]},
    {"id": 3, "name": "Мотыль", "emoji": "🟠", "price": 10, "effectiveness": "средняя", "fish_preference": [9, 16, 17, 19, 20, 28]},
    {"id": 4, "name": "Дождевой червь", "emoji": "🟤", "price": 3, "effectiveness": "низкая", "fish_preference": [11, 21, 22, 23, 29]},
    {"id": 5, "name": "Навозный червь", "emoji": "💩", "price": 4, "effectiveness": "средняя", "fish_preference": [12, 13, 14, 15, 18, 24, 30]},
    {"id": 6, "name": "Обычный червяк", "emoji": "🐛", "price": 0, "effectiveness": "очень низкая", "fish_preference": "all"}  # Бесплатный
]

# 3. Удочки (20+ реальных моделей)
RODS = [
    # Простые удочки
    {"id": 1, "name": "Поплавочная удочка", "type": "поплавочная", "emoji": "🎣", "price": 0, "durability": 50, "luck": 5, "max_weight": 3, "break_chance": 20},
    {"id": 2, "name": "Бамбуковая удочка", "type": "поплавочная", "emoji": "🎍", "price": 100, "durability": 70, "luck": 8, "max_weight": 4, "break_chance": 15},
    {"id": 3, "name": "Телескопическая удочка", "type": "поплавочная", "emoji": "📏", "price": 300, "durability": 100, "luck": 10, "max_weight": 5, "break_chance": 12},
    
    # Спиннинги
    {"id": 4, "name": "Спиннинг Shimano Catana", "type": "спиннинг", "emoji": "🎣", "price": 1500, "durability": 200, "luck": 15, "max_weight": 8, "break_chance": 8},
    {"id": 5, "name": "Спиннинг Daiwa Ninja", "type": "спиннинг", "emoji": "🎣", "price": 2500, "durability": 250, "luck": 18, "max_weight": 10, "break_chance": 7},
    {"id": 6, "name": "Спиннинг Mikado", "type": "спиннинг", "emoji": "🎣", "price": 4000, "durability": 300, "luck": 20, "max_weight": 12, "break_chance": 6},
    {"id": 7, "name": "Спиннинг Abu Garcia", "type": "спиннинг", "emoji": "🎣", "price": 6000, "durability": 350, "luck": 22, "max_weight": 15, "break_chance": 5},
    {"id": 8, "name": "Спиннинг Maximus", "type": "спиннинг", "emoji": "🎣", "price": 8000, "durability": 400, "luck": 25, "max_weight": 18, "break_chance": 4},
    
    # Зимние удочки
    {"id": 9, "name": "Зимняя удочка", "type": "зимняя", "emoji": "❄️", "price": 200, "durability": 60, "luck": 6, "max_weight": 2, "break_chance": 18},
    {"id": 10, "name": "Зимний спиннинг", "type": "зимняя", "emoji": "🎣", "price": 500, "durability": 90, "luck": 9, "max_weight": 3, "break_chance": 14},
    {"id": 11, "name": "Безмотылка", "type": "зимняя", "emoji": "⛄", "price": 800, "durability": 120, "luck": 12, "max_weight": 4, "break_chance": 10},
    
    # Нахлыст
    {"id": 12, "name": "Нахлыстовая удочка", "type": "нахлыст", "emoji": "🎣", "price": 3000, "durability": 180, "luck": 16, "max_weight": 6, "break_chance": 9},
    
    # Дорогие (премиум)
    {"id": 13, "name": "Карповая удочка", "type": "карповая", "emoji": "🐟", "price": 10000, "durability": 500, "luck": 30, "max_weight": 25, "break_chance": 3},
    {"id": 14, "name": "Морская удочка", "type": "морская", "emoji": "🌊", "price": 15000, "durability": 600, "luck": 28, "max_weight": 30, "break_chance": 2},
    {"id": 15, "name": "Элитный спиннинг", "type": "спиннинг", "emoji": "🏆", "price": 20000, "durability": 700, "luck": 35, "max_weight": 35, "break_chance": 1},
]

# 4. Рыба (100 видов из России) - упрощенная версия 30->100
FISHES = []
# Создаем 100 видов рыбы
fish_names = [
    ("Пескарь", "обычная"), ("Окунь", "обычная"), ("Карась", "обычная"), ("Плотва", "обычная"),
    ("Щука", "редкая"), ("Карп", "редкая"), ("Форель", "редкая"), ("Судак", "редкая"),
    ("Сом", "эпическая"), ("Рак", "обычная"), ("Игла-рыба", "редкая"), ("Ботинок", "мусор"),
    ("Пакет", "мусор"), ("Банка", "мусор"), ("Золотая рыбка", "легендарная"), ("Осётр", "эпическая"),
    ("Белуга", "легендарная"), ("Акула", "легендарная"), ("Кальмар", "редкая"), ("Креветка", "обычная"),
    ("Мидия", "обычная"), ("Золотая рыбка (декоративная)", "эпическая"), ("Медуза", "редкая"),
    ("Фугу", "эпическая"), ("Тунец", "редкая"), ("Лещ", "обычная"), ("Сазан", "редкая"),
    ("Лосось", "эпическая"), ("Краб", "редкая"), ("Водоросли", "мусор"),
    # Дополняем до 100
    ("Ёрш", "обычная"), ("Уклейка", "обычная"), ("Язь", "редкая"), ("Голавль", "редкая"),
    ("Жерех", "редкая"), ("Линь", "редкая"), ("Сиг", "редкая"), ("Хариус", "редкая"),
    ("Налим", "эпическая"), ("Мойва", "обычная"), ("Камбала", "редкая"), ("Треска", "редкая"),
    ("Сельдь", "обычная"), ("Корюшка", "обычная"), ("Снеток", "обычная"), ("Вобла", "обычная"),
    ("Бычок", "обычная"), ("Елец", "обычная"), ("Чехонь", "редкая"), ("Ротан", "обычная"),
    ("Змееголов", "эпическая"), ("Амур", "редкая"), ("Толстолобик", "редкая"), ("Белый амур", "редкая"),
    ("Стерлядь", "эпическая"), ("Севрюга", "эпическая"), ("Шип", "эпическая"), ("Кета", "редкая"),
    ("Горбуша", "редкая"), ("Нерка", "редкая"), ("Кижуч", "редкая"), ("Чавыча", "эпическая"),
    ("Омуль", "эпическая"), ("Муксун", "эпическая"), ("Чир", "эпическая"), ("Пыжьян", "эпическая"),
    ("Ряпушка", "обычная"), ("Сырть", "редкая"), ("Угорь", "эпическая"), ("Микижа", "эпическая"),
    ("Таймень", "легендарная"), ("Ленок", "эпическая"), ("Нельма", "легендарная"), ("Арктический голец", "эпическая"),
    ("Байкальский омуль", "эпическая"), ("Палтус", "эпическая"), ("Скат", "редкая"), ("Усач", "редкая"),
    ("Подкаменщик", "обычная"), ("Берш", "редкая"), ("Атерина", "обычная"), ("Анчоус", "обычная"),
    ("Сарган", "редкая"), ("Ставрида", "обычная"), ("Скумбрия", "обычная"), ("Сардина", "обычная"),
    ("Иваси", "обычная"), ("Тунец полосатый", "редкая"), ("Марлин", "легендарная"), ("Меч-рыба", "легендарная"),
    ("Парусник", "легендарная"), ("Дорадо", "эпическая"), ("Барабулька", "обычная"), ("Кефаль", "обычная"),
    ("Луфарь", "редкая"), ("Пеламида", "редкая"), ("Зубан", "редкая"), ("Горбыль", "редкая"),
    ("Рыба-игла", "редкая"), ("Рыба-сабля", "редкая"), ("Рыба-меч", "легендарная"), ("Рыба-пила", "легендарная"),
    ("Морской чёрт", "эпическая"), ("Скат-хвостокол", "редкая"), ("Морской конёк", "редкая"), ("Рыба-клоун", "редкая")
]

# Создаем детальную информацию для каждой рыбы
for i, (name, rarity) in enumerate(fish_names[:100], 1):
    # Определяем весовой диапазон в зависимости от редкости
    weight_ranges = {
        "обычная": (100, 3000),
        "редкая": (1000, 10000),
        "эпическая": (5000, 50000),
        "легендарная": (10000, 200000),
        "мусор": (100, 2000)
    }
    
    min_w, max_w = weight_ranges.get(rarity, (100, 1000))
    
    FISHES.append({
        "id": i,
        "name": name,
        "rarity": rarity,
        "min_weight": min_w,
        "max_weight": max_w,
        "emoji": random.choice(["🐟", "🐠", "🐡", "🦐", "🦀", "🐙", "🦞", "🐚"]),
        "price": random.randint(10, 1000)  # Цена за грамм
    })

# 5. Редкости
RARITY_PROBABILITIES = {
    "обычная": 50,
    "редкая": 30,
    "эпическая": 15,
    "легендарная": 4,
    "мусор": 1
}

# 6. Регулярные выражения
URL_PATTERN = re.compile(
    r'(https?://[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9-]+\.(com|ru|net|org|info|io|me|tv|co|us|uk|de|fr|es|it|jp|cn|рф)[^\s]*)|(t\.me/[^\s]+)|(telegram\.me/[^\s]+)|(tg://[^\s]+)'
)
USERNAME_PATTERN = re.compile(r'@[a-zA-Z0-9_]{5,32}')

# 7. Донат пакеты
DONATE_PACKAGES = [
    {"id": 1, "name": "Улучшение удочки", "price": 299, "type": "upgrade", "description": "Удочка не ломается навсегда"},
    {"id": 2, "name": "Удача +20%", "price": 200, "type": "luck", "description": "Увеличивает шанс удачи на 20%"},
    {"id": 3, "name": "Спиннинг с удачей 30%", "price": 499, "type": "rod", "description": "Спиннинг с повышенной удачей"},
    {"id": 4, "name": "Рыбопоп 100", "price": 100, "type": "fishpop", "amount": 100},
    {"id": 5, "name": "Рыбопоп 500", "price": 400, "type": "fishpop", "amount": 500},
    {"id": 6, "name": "Рыбопоп 1000", "price": 700, "type": "fishpop", "amount": 1000},
    {"id": 7, "name": "Рыбопоп 5000", "price": 3000, "type": "fishpop", "amount": 5000},
    {"id": 8, "name": "Рыбопоп 10000", "price": 5000, "type": "fishpop", "amount": 10000},
]

# Номер Тинькофф для доната
TINKOFF_CARD = "2200702034105283"

# ========== USER DATABASE ==========
class UserDatabase:
    def __init__(self):
        self.users = {}
        self.active_fishing = {}
        self.news = []
        self.transactions = []
        self.logs = []
        self.load_data()
    
    def load_data(self):
        """Загружаем все данные"""
        try:
            with open('users_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.users = data.get('users', {})
                self.news = data.get('news', [])
                self.transactions = data.get('transactions', [])
                self.logs = data.get('logs', [])
            print(f"✅ Загружено {len(self.users)} пользователей, {len(self.news)} новостей")
        except FileNotFoundError:
            print("📁 Файл данных не найден, начинаем с чистого листа")
            self.users = {}
            self.news = []
            self.transactions = []
            self.logs = []
        except Exception as e:
            print(f"⚠️ Ошибка загрузки данных: {e}")
            self.users = {}
            self.news = []
            self.transactions = []
            self.logs = []
    
    def save_data(self):
        """Сохраняем все данные"""
        try:
            data = {
                'users': self.users,
                'news': self.news,
                'transactions': self.transactions,
                'logs': self.logs
            }
            with open('users_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("💾 Данные сохранены")
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            # Инициализация нового пользователя
            self.users[user_id] = {
                'worms': INITIAL_BASIC_WORMS,
                'baits': {str(bait['id']): 0 for bait in BAITS},
                'baits']['6'] = 10,  # 10 обычных червяков
                'rods': ['1'],  # ID удочек
                'active_rod': '1',
                'rod_durability': {str(rod['id']): rod['durability'] for rod in RODS if str(rod['id']) in ['1']},
                'fish_caught': [],
                'total_fish': 0,
                'total_weight': 0,
                'money': 0,
                'fishpop': 0,
                'last_fishing_time': None,
                'last_worm_refill': time.time(),
                'stats': {'common': 0, 'rare': 0, 'epic': 0, 'legendary': 0, 'trash': 0},
                'username': None,
                'first_name': None,
                'warnings': [],
                'banned_until': None,
                'location': '1',  # ID водоема
                'upgrades': {
                    'unbreakable': False,
                    'luck_boost': 0
                },
                'daily_task': None,
                'last_daily': None
            }
        
        user = self.users[user_id]
        current_time = time.time()
        
        # Автопополнение обычных червяков
        time_passed = current_time - user.get('last_worm_refill', current_time)
        worms_to_add = int(time_passed // WORM_REFILL_TIME)
        
        if worms_to_add > 0:
            max_add = MAX_BASIC_WORMS - user['baits'].get('6', 0)
            if max_add > 0:
                add_amount = min(worms_to_add, max_add)
                user['baits']['6'] = user['baits'].get('6', 0) + add_amount
                user['last_worm_refill'] = current_time
        
        # Очистка предупреждений
        user['warnings'] = [w for w in user['warnings'] if current_time - w < WARNING_EXPIRE_TIME]
        
        return user
    
    def add_log(self, action, user_id, details, admin_id=None):
        """Добавляем запись в лог"""
        log_entry = {
            'timestamp': time.time(),
            'action': action,
            'user_id': str(user_id),
            'admin_id': str(admin_id) if admin_id else None,
            'details': details
        }
        self.logs.append(log_entry)
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
        self.save_data()
    
    def add_news(self, text, author_id):
        """Добавляем новость"""
        news_entry = {
            'id': len(self.news) + 1,
            'text': text,
            'author_id': str(author_id),
            'timestamp': time.time(),
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.news.append(news_entry)
        self.save_data()
        return news_entry
    
    def get_news(self, limit=10):
        """Получаем последние новости"""
        return sorted(self.news, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    def add_transaction(self, user_id, package_id, amount, screenshot=None):
        """Добавляем транзакцию"""
        transaction = {
            'id': len(self.transactions) + 1,
            'user_id': str(user_id),
            'package_id': package_id,
            'amount': amount,
            'timestamp': time.time(),
            'status': 'pending',
            'screenshot': screenshot
        }
        self.transactions.append(transaction)
        self.save_data()
        return transaction
    
    def complete_transaction(self, transaction_id, admin_id):
        """Завершаем транзакцию"""
        for transaction in self.transactions:
            if transaction['id'] == transaction_id:
                transaction['status'] = 'completed'
                transaction['completed_by'] = str(admin_id)
                transaction['completed_at'] = time.time()
                self.save_data()
                return True
        return False
    
    def use_bait(self, user_id):
        """Используем наживку"""
        user = self.get_user(user_id)
        
        # Получаем доступные наживки (кроме обычных червяков)
        available_baits = []
        for bait_id, count in user['baits'].items():
            if count > 0 and bait_id != '6':  # Исключаем обычных червяков
                for _ in range(count):
                    available_baits.append(bait_id)
        
        if not available_baits:
            # Используем обычного червяка
            if user['baits'].get('6', 0) > 0:
                user['baits']['6'] -= 1
                self.save_data()
                return '6', user['baits']['6']
            else:
                return None, 0
        
        # Выбираем случайную наживку
        selected_bait = random.choice(available_baits)
        user['baits'][selected_bait] -= 1
        self.save_data()
        
        return selected_bait, user['baits'][selected_bait]
    
    def add_bait(self, user_id, bait_id, amount):
        """Добавляем наживку"""
        user = self.get_user(user_id)
        user['baits'][str(bait_id)] = user['baits'].get(str(bait_id), 0) + amount
        self.save_data()
        return user['baits'][str(bait_id)]
    
    def add_rod(self, user_id, rod_id):
        """Добавляем удочку"""
        user = self.get_user(user_id)
        rod_str = str(rod_id)
        
        if rod_str not in user['rods']:
            user['rods'].append(rod_str)
            user['rod_durability'][rod_str] = next((r['durability'] for r in RODS if str(r['id']) == rod_str), 100)
            self.save_data()
            return True
        return False
    
    def use_rod(self, user_id, fish_weight):
        """Используем удочку, проверяем поломку"""
        user = self.get_user(user_id)
        rod_id = user.get('active_rod', '1')
        
        if user['upgrades']['unbreakable']:
            return rod_id, user['rod_durability'].get(rod_id, 100), False
        
        rod_info = next((r for r in RODS if str(r['id']) == rod_id), None)
        if not rod_info:
            return rod_id, 100, False
        
        # Уменьшаем прочность
        current_durability = user['rod_durability'].get(rod_id, rod_info['durability'])
        wear_amount = max(1, int(fish_weight / 1000))  # Износ зависит от веса
        new_durability = max(0, current_durability - wear_amount)
        user['rod_durability'][rod_id] = new_durability
        
        # Проверяем поломку
        broken = False
        if new_durability <= 0:
            # Удочка сломалась
            if rod_id in user['rods']:
                user['rods'].remove(rod_id)
            if rod_id in user['rod_durability']:
                del user['rod_durability'][rod_id]
            # Автоматически выбираем другую удочку
            if user['rods']:
                user['active_rod'] = user['rods'][0]
            else:
                user['active_rod'] = '1'
                user['rods'] = ['1']
                user['rod_durability']['1'] = 100
            broken = True
        
        self.save_data()
        return rod_id, new_durability, broken
    
    def repair_rod(self, user_id, rod_id):
        """Ремонтируем удочку"""
        user = self.get_user(user_id)
        rod_str = str(rod_id)
        
        if rod_str in user['rod_durability']:
            rod_info = next((r for r in RODS if str(r['id']) == rod_id), None)
            if rod_info:
                user['rod_durability'][rod_str] = rod_info['durability']
                self.save_data()
                return True
        return False
    
    def add_fish(self, user_id, fish, exact_weight):
        """Добавляем пойманную рыбу"""
        user = self.get_user(user_id)
        
        # Рассчитываем стоимость
        price_per_gram = fish.get('price', 10)
        fish_value = int(exact_weight * price_per_gram / 1000)  # Цена за кг
        
        catch = {
            'fish_id': fish['id'],
            'name': fish['name'],
            'rarity': fish['rarity'],
            'weight': exact_weight,
            'value': fish_value,
            'emoji': fish['emoji'],
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        user['fish_caught'].append(catch)
        if len(user['fish_caught']) > 50:
            user['fish_caught'] = user['fish_caught'][-50:]
        
        user['total_fish'] += 1
        user['total_weight'] += exact_weight
        user['money'] += fish_value
        
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
        self.save_data()
        return catch
    
    def add_warning(self, user_id, chat_id=None):
        user = self.get_user(user_id)
        current_time = time.time()
        user['warnings'].append(current_time)
        
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
    
    def get_top_players(self, by='fish', limit=10):
        """Топ игроков по разным критериям"""
        users_list = []
        
        for user_id, user_data in self.users.items():
            if by == 'fish':
                score = user_data.get('total_fish', 0)
            elif by == 'weight':
                score = user_data.get('total_weight', 0)
            elif by == 'money':
                score = user_data.get('money', 0)
            elif by == 'fishpop':
                score = user_data.get('fishpop', 0)
            else:
                score = 0
            
            users_list.append({
                'user_id': user_id,
                'username': user_data.get('username', 'Неизвестно'),
                'first_name': user_data.get('first_name', 'Игрок'),
                'score': score
            })
        
        return sorted(users_list, key=lambda x: x['score'], reverse=True)[:limit]

db = UserDatabase()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def calculate_catch_with_bait(bait_id, location_id, user_luck=0):
    """Рассчитываем улов с учетом наживки и локации"""
    # Получаем рыбу доступную в локации
    location = next((loc for loc in WATER_BODIES if str(loc['id']) == str(location_id)), WATER_BODIES[0])
    available_fish_ids = location.get('fish', list(range(1, 31)))
    
    # Фильтруем рыбу по предпочтениям наживки
    bait_info = next((b for b in BAITS if str(b['id']) == str(bait_id)), BAITS[-1])
    preferred_fish = bait_info.get('fish_preference', [])
    
    if preferred_fish == "all":
        # Все рыбы доступны
        filtered_fish = [f for f in FISHES if f['id'] in available_fish_ids]
    else:
        # Только предпочитаемая рыба
        filtered_fish = [f for f in FISHES if f['id'] in available_fish_ids and f['id'] in preferred_fish]
    
    if not filtered_fish:
        filtered_fish = [f for f in FISHES if f['id'] in available_fish_ids]
    
    # Учитываем удачу пользователя
    total_prob = sum(RARITY_PROBABILITIES.values())
    luck_adjustment = user_luck  # Проценты удачи
    adjusted_prob = min(100, max(0, total_prob + luck_adjustment))
    
    rand_num = random.randint(1, 100)
    
    # Скорректированные вероятности с учетом удачи
    adjusted_probs = {
        "обычная": max(0, 50 - luck_adjustment/2),
        "редкая": 30,
        "эпическая": 15 + luck_adjustment/2,
        "легендарная": 4 + luck_adjustment/3,
        "мусор": max(0, 1 - luck_adjustment/4)
    }
    
    # Нормализуем вероятности
    total_adj = sum(adjusted_probs.values())
    if total_adj > 0:
        for key in adjusted_probs:
            adjusted_probs[key] = adjusted_probs[key] * 100 / total_adj
    
    # Выбираем редкость
    current_prob = 0
    selected_rarity = "обычная"
    rand_rarity = random.random() * 100
    
    for rarity, prob in adjusted_probs.items():
        current_prob += prob
        if rand_rarity <= current_prob:
            selected_rarity = rarity
            break
    
    # Выбираем конкретную рыбу этой редкости из доступных
    available_by_rarity = [f for f in filtered_fish if f['rarity'] == selected_rarity]
    if not available_by_rarity:
        available_by_rarity = [f for f in filtered_fish if f['rarity'] == "обычная"]
    
    if not available_by_rarity:
        return None
    
    selected_fish = random.choice(available_by_rarity)
    
    # Генерируем точный вес
    exact_weight = random.randint(selected_fish['min_weight'], selected_fish['max_weight'])
    
    return selected_fish, exact_weight

def create_main_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('🎣 Начать рыбалку')
    btn2 = types.KeyboardButton('📍 Сменить водоем')
    btn3 = types.KeyboardButton('🛒 Магазин')
    btn4 = types.KeyboardButton('📊 Статистика')
    btn5 = types.KeyboardButton('🎒 Инвентарь')
    btn6 = types.KeyboardButton('🏆 Топ игроков')
    btn7 = types.KeyboardButton('📰 Новости')
    btn8 = types.KeyboardButton('💰 Донат')
    btn9 = types.KeyboardButton('❓ Помощь')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8, btn9)
    return markup

def create_fishing_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton('🎣 Забросить удочку')
    btn2 = types.KeyboardButton('📋 Меню')
    markup.add(btn1, btn2)
    return markup

def create_location_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for location in WATER_BODIES:
        btn = types.KeyboardButton(f"{location['emoji']} {location['name']}")
        markup.add(btn)
    btn_back = types.KeyboardButton('⬅️ Назад')
    markup.add(btn_back)
    return markup

def create_shop_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('🪱 Купить наживку')
    btn2 = types.KeyboardButton('🎣 Купить удочку')
    btn3 = types.KeyboardButton('🔧 Ремонт удочек')
    btn4 = types.KeyboardButton('⬅️ Назад')
    markup.add(btn1, btn2, btn3, btn4)
    return markup

def create_admin_keyboard(level=5):
    """Создаем клавиатуру админа в зависимости от уровня"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if level >= 1:
        btn1 = types.KeyboardButton('👑 Админ панель')
        btn2 = types.KeyboardButton('📋 Список игроков')
        markup.add(btn1, btn2)
    
    if level >= 5:
        btn3 = types.KeyboardButton('⚡ Выдать награду')
        btn4 = types.KeyboardButton('⚠️ Выдать предупреждение')
        btn5 = types.KeyboardButton('🚫 Забанить')
        btn6 = types.KeyboardButton('✅ Снять бан')
        btn7 = types.KeyboardButton('📢 Отправить новость')
        btn8 = types.KeyboardButton('📊 Логи действий')
        markup.add(btn3, btn4, btn5, btn6, btn7, btn8)
    
    btn_back = types.KeyboardButton('⬅️ В меню')
    markup.add(btn_back)
    return markup

def ban_user_in_group(chat_id, user_id, user_name):
    try:
        bot.ban_chat_member(chat_id, user_id, until_date=int(time.time()) + BAN_DURATION)
        ban_message = f"🚫 {user_name} забанен на 2 дня!\n⚠️ Причина: 2 ссылки за 24 часа"
        bot.send_message(chat_id, ban_message)
        return True
    except Exception as e:
        print(f"Ошибка бана: {e}")
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
                    
                    if db.is_banned(user_id):
                        ban_time_left = db.get_ban_time_left(user_id)
                        days_left = int(ban_time_left // 86400)
                        hours_left = int((ban_time_left % 86400) // 3600)
                        minutes_left = int((ban_time_left % 3600) // 60)
                        
                        ban_message = (
                            f"🚫 {user.first_name}, ты уже забанен!\n"
                            f"⏳ Бан истечет через: {days_left}д {hours_left}ч {minutes_left}мин"
                        )
                        bot.send_message(chat_id, ban_message)
                        return True
                    
                    bot.delete_message(chat_id, message.message_id)
                    banned, warning_count, is_ban = db.add_warning(user_id, chat_id)
                    
                    if is_ban:
                        ban_user_in_group(chat_id, user.id, user.first_name)
                    else:
                        warning_message = (
                            f"⚠️ {user.first_name}, даю предупреждение!\n"
                            f"На 2 раз даю бан, не кидай ссылки\n"
                            f"📊 Предупреждений: {warning_count}/2"
                        )
                        bot.send_message(chat_id, warning_message)
                    
                except Exception as e:
                    print(f"Ошибка удаления ссылки: {e}")
                return True
    return False

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    user_id_str = str(user.id)
    user_data = db.get_user(user.id)
    
    # Обновляем имя пользователя если изменилось
    user_data['username'] = user.username
    user_data['first_name'] = user.first_name
    
    if db.is_banned(user_id_str):
        ban_time_left = db.get_ban_time_left(user.id)
        days_left = int(ban_time_left // 86400)
        hours_left = int((ban_time_left % 86400) // 3600)
        minutes_left = int((ban_time_left % 3600) // 60)
        
        ban_text = (
            f"🚫 {user.first_name}, ты забанен!\n\n"
            f"⏳ Бан истечет через: {days_left}д {hours_left}ч {minutes_left}мин\n"
            f"Ожидайте окончания бана для продолжения игры."
        )
        bot.send_message(message.chat.id, ban_text)
        return
    
    # Проверяем является ли пользователь админом
    admin_level = ADMINS.get(user_id_str, 0)
    
    welcome_text = (
        f"🎣 Привет, {user.first_name}!\n"
        f"Добро пожаловать в расширенный мир рыбалки!\n\n"
        f"📍 Текущий водоем: {WATER_BODIES[0]['name']}\n"
        f"🪱 Наживка: {sum(user_data['baits'].values())} шт\n"
        f"🎣 Активная удочка: {next((r['name'] for r in RODS if str(r['id']) == user_data.get('active_rod', '1')), 'Поплавочная')}\n"
        f"💰 Деньги: {user_data['money']} руб\n"
        f"🏆 Рыбопоп: {user_data.get('fishpop', 0)}\n\n"
        f"Используй кнопки ниже для игры!\n\n"
        f"Если хотите поддержать: ||{TINKOFF_CARD}||"
    )
    
    if admin_level > 0:
        welcome_text += f"\n\n👑 Уровень админа: {admin_level}"
        bot.send_message(message.chat.id, welcome_text, reply_markup=create_admin_keyboard(admin_level))
    else:
        bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['help'])
def help_command(message):
    help_text = (
        "🎣 *Помощь по игре \"Рыбалка\"*\n\n"
        "📋 *Основные команды:*\n"
        "/start - Начать игру\n"
        "/fishing - Начать рыбалку\n"
        "/stats - Ваша статистика\n"
        "/inventory - Последние уловы\n"
        "/top - Топ игроков\n"
        "/news - Последние новости\n"
        "/donate - Поддержать проект\n"
        "/help - Эта справка\n\n"
        "🎮 *Как играть:*\n"
        "1️⃣ Выберите водоем (разная рыба в разных местах)\n"
        "2️⃣ Купите наживку в магазине\n"
        "3️⃣ Выберите удочку\n"
        "4️⃣ Начните рыбалку\n"
        "5️⃣ Каждая рыбалка использует 1 наживку\n"
        "6️⃣ Удочки имеют прочность и могут сломаться\n\n"
        "🪱 *Наживки:*\n"
        "• ⚪ Белый опарыш - для мелкой рыбы\n"
        "• 🔴 Красный опарыш - для хищной рыбы\n"
        "• 🟠 Мотыль - для ценной рыбы\n"
        "• 🟤 Дождевой червь - универсальный\n"
        "• 💩 Навозный червь - для донной рыбы\n"
        "• 🐛 Обычный червяк - бесплатный\n\n"
        "🎣 *Удочки:*\n"
        "• Разные типы: поплавочные, спиннинги, зимние\n"
        "• У каждой своя прочность и максимальный вес\n"
        "• Удочки ломаются - ремонтируйте в магазине\n"
        "• Улучшения: вечная прочность, удача +20%\n\n"
        "🐟 *Редкости рыбы (100 видов):*\n"
        "• 🐟 Обычная (50%)\n"
        "• 🐠 Редкая (30%)\n"
        "• 🌟 Эпическая (15%)\n"
        "• 👑 Легендарная (4%)\n"
        "• 🗑️ Мусор (1%)\n\n"
        "⚖️ *Правила чата:*\n"
        "• Запрещены любые ссылки (кроме @username)\n"
        "• 1 ссылка = предупреждение\n"
        "• 2 ссылки за 24 часа = бан на 2 дня\n\n"
        "💰 *Донат:*\n"
        "• Улучшения удочек\n"
        "• Бонусы удачи\n"
        "• Рыбопоп (внутренняя валюта)\n"
        "• Поддержка развития проекта\n\n"
        "Удачи на рыбалке! 🎣"
    )
    
    bot.send_message(message.chat.id, help_text, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['stats'])
def stats_command(message):
    user = message.from_user
    user_id_str = str(user.id)
    
    if db.is_banned(user_id_str):
        return
    
    user_data = db.get_user(user.id)
    total = user_data['total_fish']
    
    if total > 0:
        luck_rate = ((user_data['stats']['epic'] + user_data['stats']['legendary']) / total * 100)
        trash_rate = (user_data['stats']['trash'] / total * 100)
        avg_weight = user_data['total_weight'] / total if total > 0 else 0
    else:
        luck_rate = trash_rate = avg_weight = 0
    
    warning_count = db.get_warning_count(user.id)
    
    # Текущая удочка
    active_rod_id = user_data.get('active_rod', '1')
    rod_info = next((r for r in RODS if str(r['id']) == active_rod_id), RODS[0])
    rod_durability = user_data['rod_durability'].get(active_rod_id, rod_info['durability'])
    
    # Текущий водоем
    location_id = user_data.get('location', '1')
    location = next((loc for loc in WATER_BODIES if str(loc['id']) == location_id), WATER_BODIES[0])
    
    stats_text = (
        f"📊 *Статистика {user.first_name}*\n\n"
        f"📍 *Водоем:* {location['emoji']} {location['name']}\n"
        f"🎣 *Удочка:* {rod_info['name']} ({rod_durability}/{rod_info['durability']})\n"
        f"💰 *Деньги:* {user_data['money']} руб | 🏆 *Рыбопоп:* {user_data.get('fishpop', 0)}\n\n"
        f"🪱 *Наживка:*\n"
    )
    
    # Добавляем информацию о наживке
    for bait in BAITS:
        count = user_data['baits'].get(str(bait['id']), 0)
        if count > 0:
            stats_text += f"{bait['emoji']} {bait['name']}: {count} шт\n"
    
    stats_text += f"\n🎣 *Рыбалка:*\n"
    stats_text += f"• Всего попыток: {user_data['total_fish']}\n"
    stats_text += f"• Общий вес: {user_data['total_weight']/1000:.1f} кг\n"
    stats_text += f"• Средний вес: {avg_weight:.0f} г\n"
    stats_text += f"• Предупреждений: {warning_count}/2\n\n"
    
    stats_text += f"🐟 *Поймано:*\n"
    stats_text += f"• 🐟 Обычных: {user_data['stats']['common']}\n"
    stats_text += f"• 🐠 Редких: {user_data['stats']['rare']}\n"
    stats_text += f"• 🌟 Эпических: {user_data['stats']['epic']}\n"
    stats_text += f"• 👑 Легендарных: {user_data['stats']['legendary']}\n"
    stats_text += f"• 🗑️ Мусора: {user_data['stats']['trash']}\n\n"
    
    stats_text += f"🎯 Удача: {luck_rate:.1f}% | Мусор: {trash_rate:.1f}%\n"
    
    if user_data['upgrades']['unbreakable']:
        stats_text += f"🔧 Улучшение: Вечная удочка ✅\n"
    if user_data['upgrades']['luck_boost'] > 0:
        stats_text += f"🍀 Удача: +{user_data['upgrades']['luck_boost']}% ✅\n"
    
    bot.send_message(message.chat.id, stats_text, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['inventory'])
def inventory_command(message):
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    user_data = db.get_user(user.id)
    
    # Информация об удочках
    inventory_text = f"🎒 *Инвентарь {user.first_name}:*\n\n"
    
    inventory_text += "🎣 *Удочки:*\n"
    for rod_id in user_data.get('rods', ['1']):
        rod_info = next((r for r in RODS if str(r['id']) == rod_id), None)
        if rod_info:
            durability = user_data['rod_durability'].get(rod_id, rod_info['durability'])
            is_active = " (активная)" if rod_id == user_data.get('active_rod', '1') else ""
            inventory_text += f"{rod_info['emoji']} {rod_info['name']}: {durability}/{rod_info['durability']}{is_active}\n"
    
    inventory_text += "\n🪱 *Наживка:*\n"
    total_baits = 0
    for bait in BAITS:
        count = user_data['baits'].get(str(bait['id']), 0)
        if count > 0:
            inventory_text += f"{bait['emoji']} {bait['name']}: {count} шт\n"
            total_baits += count
    
    inventory_text += f"\n📦 Всего наживки: {total_baits} шт\n\n"
    
    # Последние уловы
    if not user_data['fish_caught']:
        inventory_text += "🐟 Последние уловы: пока пусто"
    else:
        inventory_text += "🐟 *Последние уловы:*\n"
        for i, catch in enumerate(reversed(user_data['fish_caught'][-5:]), 1):
            inventory_text += f"{i}. {catch['emoji']} {catch['name']} ({catch['weight']}г) - {catch['value']} руб\n"
    
    bot.send_message(message.chat.id, inventory_text, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['fishing'])
def fishing_command_handler(message):
    user = message.from_user
    user_id_str = str(user.id)
    
    if db.is_banned(user_id_str):
        return
    
    if delete_links_in_group(message):
        return
    
    user_id = str(user.id)
    
    if user_id in db.active_fishing:
        bot.send_message(message.chat.id, "⏳ Вы уже рыбачите! Подождите...", reply_markup=create_fishing_keyboard())
        return
    
    user_data = db.get_user(user.id)
    
    # Проверяем есть ли наживка
    total_baits = sum(user_data['baits'].values())
    if total_baits <= 0:
        bot.send_message(message.chat.id,
                       "😔 Наживка закончилась!\n"
                       "Купите наживку в магазине 🛒",
                       reply_markup=create_main_keyboard())
        return
    
    # Начинаем рыбалку
    msg = bot.send_message(message.chat.id,
                          f"🎣 *Началась рыбалка!*\n\n"
                          f"📍 Водоем: {WATER_BODIES[int(user_data.get('location', 1))-1]['name']}\n"
                          f"🎣 Удочка: {next((r['name'] for r in RODS if str(r['id']) == user_data.get('active_rod', '1')), 'Поплавочная')}\n"
                          f"⏳ Рыбалка продлится {FISHING_TIME} секунд\n\n"
                          f"Ждите... рыба клюёт!",
                          reply_markup=create_fishing_keyboard())
    
    def fishing_timer():
        time.sleep(FISHING_TIME)
        
        if user_id not in db.active_fishing:
            return
        
        del db.active_fishing[user_id]
        
        # Используем наживку
        bait_id, bait_left = db.use_bait(user.id)
        bait_info = next((b for b in BAITS if str(b['id']) == bait_id), BAITS[-1])
        
        # Рассчитываем улов
        user_data = db.get_user(user.id)
        location_id = user_data.get('location', '1')
        user_luck = user_data['upgrades'].get('luck_boost', 0)
        
        result = calculate_catch_with_bait(bait_id, location_id, user_luck)
        
        if not result:
            bot.send_message(message.chat.id, "❌ Ошибка при расчете улова", reply_markup=create_main_keyboard())
            return
        
        fish, exact_weight = result
        
        # Проверяем удочку
        rod_id, durability, broken = db.use_rod(user.id, exact_weight)
        rod_info = next((r for r in RODS if str(r['id']) == rod_id), RODS[0])
        
        # Добавляем рыбу
        catch_info = db.add_fish(user.id, fish, exact_weight)
        
        rarity_emojis = {
            'обычная': '🐟',
            'редкая': '🐠',
            'эпическая': '🌟',
            'легендарная': '👑',
            'мусор': '🗑️'
        }
        
        result_text = (
            f"🎉 *Рыбалка завершена!*\n\n"
            f"🪱 Использована наживка: {bait_info['emoji']} {bait_info['name']}\n"
            f"📊 Осталось: {bait_left} шт\n\n"
            f"{rarity_emojis.get(fish['rarity'], '🎣')} *Поймано:* {fish['name']}\n"
            f"⚖️ *Вес:* {exact_weight} г ({exact_weight/1000:.2f} кг)\n"
            f"💰 *Стоимость:* {catch_info['value']} руб\n"
            f"📊 *Редкость:* {fish['rarity']}\n\n"
            f"🎣 Удочка: {rod_info['name']}\n"
            f"🔧 Прочность: {durability}/{rod_info['durability']}\n"
            f"💰 Баланс: {db.get_user(user.id)['money']} руб\n"
        )
        
        if broken:
            result_text += "\n⚠️ *Удочка сломалась!* Купите новую в магазине.\n"
        
        if fish['rarity'] == 'легендарная':
            result_text += "\n🎊 *ВАУ! Легендарная рыба!* 🎊\n"
        elif fish['rarity'] == 'мусор':
            result_text += "\n😔 Не повезло... Попробуйте еще раз!\n"
        
        if durability < rod_info['durability'] * 0.3:
            result_text += f"\n🔴 *Внимание!* Удочка почти сломана ({durability}%). Ремонтируйте!\n"
        
        try:
            bot.send_message(message.chat.id, result_text, reply_markup=create_main_keyboard())
        except Exception as e:
            print(f"Ошибка отправки: {e}")
    
    db.active_fishing[user_id] = threading.Thread(target=fishing_timer)
    db.active_fishing[user_id].daemon = True
    db.active_fishing[user_id].start()

@bot.message_handler(commands=['top'])
def top_command(message):
    """Топ игроков"""
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    # Создаем inline клавиатуру для выбора типа топа
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🐟 По рыбе", callback_data="top_fish")
    btn2 = types.InlineKeyboardButton("⚖️ По весу", callback_data="top_weight")
    btn3 = types.InlineKeyboardButton("💰 По деньгам", callback_data="top_money")
    btn4 = types.InlineKeyboardButton("🏆 По рыбопопу", callback_data="top_fishpop")
    markup.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(message.chat.id, "🏆 *Топ игроков*\nВыберите категорию:", 
                    reply_markup=markup, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('top_'))
def handle_top_callback(call):
    top_type = call.data.split('_')[1]
    
    if top_type == 'fish':
        top_data = db.get_top_players('fish', 10)
        title = "🐟 Топ игроков по количеству рыбы"
    elif top_type == 'weight':
        top_data = db.get_top_players('weight', 10)
        title = "⚖️ Топ игроков по общему весу"
    elif top_type == 'money':
        top_data = db.get_top_players('money', 10)
        title = "💰 Топ игроков по деньгам"
    else:  # fishpop
        top_data = db.get_top_players('fishpop', 10)
        title = "🏆 Топ игроков по рыбопопу"
    
    top_text = f"*{title}*\n\n"
    
    for i, player in enumerate(top_data, 1):
        username = player['username'] if player['username'] else player['first_name']
        score = player['score']
        
        if top_type == 'weight':
            score_text = f"{score/1000:.1f} кг"
        elif top_type == 'money':
            score_text = f"{score} руб"
        else:
            score_text = str(score)
        
        medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟']
        medal = medals[i-1] if i <= len(medals) else f"{i}."
        
        top_text += f"{medal} {username}: {score_text}\n"
    
    if not top_data:
        top_text = "📭 Пока нет данных для топа"
    
    try:
        bot.edit_message_text(top_text, call.message.chat.id, call.message.message_id, 
                            parse_mode='Markdown')
    except:
        bot.send_message(call.message.chat.id, top_text, parse_mode='Markdown')

@bot.message_handler(commands=['news'])
def news_command(message):
    """Показать последние новости"""
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    news_list = db.get_news(5)
    
    if not news_list:
        news_text = "📰 *Новости*\n\nПока нет новостей. Следите за обновлениями!"
    else:
        news_text = "📰 *Последние новости*\n\n"
        for news in news_list:
            date = datetime.fromtimestamp(news['timestamp']).strftime("%d.%m.%Y %H:%M")
            news_text += f"📅 *{date}*\n{news['text']}\n\n{'─'*30}\n\n"
    
    bot.send_message(message.chat.id, news_text, parse_mode='Markdown', 
                    reply_markup=create_main_keyboard())

@bot.message_handler(commands=['donate'])
def donate_command(message):
    """Информация о донате"""
    user = message.from_user
    user_id_str = str(user.id)
    
    if db.is_banned(user_id_str):
        return
    
    donate_text = (
        f"💰 *Поддержать проект*\n\n"
        f"Ваша поддержка помогает развивать бота!\n\n"
        f"💳 *Номер карты Тинькофф:*\n"
        f"`{TINKOFF_CARD}`\n\n"
        f"📦 *Доступные пакеты:*\n"
    )
    
    for package in DONATE_PACKAGES:
        donate_text += f"\n*{package['name']}* - {package['price']} руб\n"
        if 'description' in package:
            donate_text += f"  {package['description']}\n"
        elif package['type'] == 'fishpop':
            donate_text += f"  {package['amount']} рыбопоп\n"
    
    donate_text += "\n\n*Как получить награду:*\n"
    donate_text += "1. Выберите пакет\n"
    donate_text += "2. Переведите сумму на карту\n"
    donate_text += "3. Отправьте скриншот перевода\n"
    donate_text += "4. Получите награду в течение 24 часов\n\n"
    donate_text += "Для выбора пакета нажмите кнопку '💰 Донат' в меню"
    
    # Создаем inline кнопку для быстрого выбора пакета
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🎁 Выбрать пакет", callback_data="select_package"))
    
    bot.send_message(message.chat.id, donate_text, parse_mode='Markdown', 
                    reply_markup=markup)

# ========== ОБРАБОТЧИКИ КНОПОК ==========
@bot.message_handler(func=lambda msg: msg.text == '🎣 Начать рыбалку')
def fishing_button_handler(message):
    fishing_command_handler(message)

@bot.message_handler(func=lambda msg: msg.text == '🎣 Забросить удочку')
def fishing_cast_handler(message):
    fishing_command_handler(message)

@bot.message_handler(func=lambda msg: msg.text == '📍 Сменить водоем')
def location_button_handler(message):
    """Показать список водоемов"""
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    user_data = db.get_user(user.id)
    current_location_id = user_data.get('location', '1')
    current_location = next((loc for loc in WATER_BODIES if str(loc['id']) == current_location_id), WATER_BODIES[0])
    
    locations_text = f"📍 *Текущий водоем:* {current_location['emoji']} {current_location['name']}\n\n"
    locations_text += "*Выберите новый водоем:*\n\n"
    
    for location in WATER_BODIES:
        fish_count = len(location['fish'])
        locations_text += f"{location['emoji']} *{location['name']}*\n"
        locations_text += f"  📍 {location['region']}\n"
        locations_text += f"  🐟 Рыбы: {fish_count} видов\n"
        locations_text += f"  🌊 Глубина: {location['depth']}\n\n"
    
    locations_text += "💡 *Совет:* Разная рыба водится в разных водоемах!"
    
    bot.send_message(message.chat.id, locations_text, parse_mode='Markdown',
                    reply_markup=create_location_keyboard())

@bot.message_handler(func=lambda msg: any(msg.text == f"{loc['emoji']} {loc['name']}" for loc in WATER_BODIES))
def select_location_handler(message):
    """Обработка выбора водоема"""
    user = message.from_user
    user_data = db.get_user(user.id)
    
    # Находим выбранный водоем
    for location in WATER_BODIES:
        if message.text == f"{location['emoji']} {location['name']}":
            user_data['location'] = str(location['id'])
            db.save_data()
            
            response_text = (
                f"📍 *Водоем изменен!*\n\n"
                f"{location['emoji']} *{location['name']}*\n"
                f"📌 Регион: {location['region']}\n"
                f"🌊 Глубина: {location['depth']}\n"
                f"🐟 Видов рыбы: {len(location['fish'])}\n\n"
                f"Теперь вы можете ловить рыбу в этом водоеме!"
            )
            
            bot.send_message(message.chat.id, response_text, parse_mode='Markdown',
                           reply_markup=create_main_keyboard())
            return

@bot.message_handler(func=lambda msg: msg.text == '🛒 Магазин')
def shop_button_handler(message):
    """Показать магазин"""
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    user_data = db.get_user(user.id)
    
    shop_text = (
        f"🛒 *Магазин*\n\n"
        f"💰 Ваш баланс: {user_data['money']} руб\n"
        f"🏆 Рыбопоп: {user_data.get('fishpop', 0)}\n\n"
        f"Выберите категорию:"
    )
    
    bot.send_message(message.chat.id, shop_text, parse_mode='Markdown',
                    reply_markup=create_shop_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '🪱 Купить наживку')
def buy_bait_button_handler(message):
    """Покупка наживки"""
    user = message.from_user
    user_data = db.get_user(user.id)
    
    # Создаем inline клавиатуру с наживкой
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for bait in BAITS:
        if bait['price'] > 0:  # Платные наживки
            btn_text = f"{bait['emoji']} {bait['name']} - {bait['price']} руб"
            callback_data = f"buy_bait_{bait['id']}"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    bait_text = (
        f"🪱 *Купить наживку*\n\n"
        f"💰 Ваш баланс: {user_data['money']} руб\n\n"
        f"*Доступная наживка:*\n"
    )
    
    for bait in BAITS:
        if bait['price'] > 0:
            bait_text += f"\n{bait['emoji']} *{bait['name']}* - {bait['price']} руб\n"
            bait_text += f"  🎯 Эффективность: {bait['effectiveness']}\n"
    
    bait_text += "\n💡 *Совет:* Разная наживка приманивает разную рыбу!"
    
    bot.send_message(message.chat.id, bait_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_bait_'))
def handle_buy_bait_callback(call):
    """Обработка покупки наживки"""
    user = call.from_user
    user_id_str = str(user.id)
    bait_id = call.data.split('_')[2]
    
    user_data = db.get_user(user.id)
    bait_info = next((b for b in BAITS if str(b['id']) == bait_id), None)
    
    if not bait_info:
        bot.answer_callback_query(call.id, "❌ Наживка не найдена")
        return
    
    if user_data['money'] < bait_info['price']:
        bot.answer_callback_query(call.id, "❌ Недостаточно денег")
        return
    
    # Покупаем 1 наживку
    user_data['money'] -= bait_info['price']
    new_count = db.add_bait(user.id, bait_id, 1)
    
    # Логируем покупку
    db.add_log('buy_bait', user.id, f"{bait_info['name']} за {bait_info['price']} руб")
    
    response_text = (
        f"✅ *Покупка успешна!*\n\n"
        f"🪱 Куплено: {bait_info['emoji']} {bait_info['name']}\n"
        f"💰 Стоимость: {bait_info['price']} руб\n"
        f"📦 Теперь у вас: {new_count} шт\n"
        f"💳 Осталось денег: {user_data['money']} руб"
    )
    
    try:
        bot.edit_message_text(response_text, call.message.chat.id, call.message.message_id,
                            parse_mode='Markdown')
    except:
        bot.send_message(call.message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '🎣 Купить удочку')
def buy_rod_button_handler(message):
    """Покупка удочки"""
    user = message.from_user
    user_data = db.get_user(user.id)
    
    # Группируем удочки по типам
    rods_by_type = {}
    for rod in RODS:
        if rod['price'] > 0:  # Платные удочки
            if rod['type'] not in rods_by_type:
                rods_by_type[rod['type']] = []
            rods_by_type[rod['type']].append(rod)
    
    # Создаем inline клавиатуру
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for rod_type, rods in rods_by_type.items():
        for rod in rods:
            # Проверяем, есть ли уже такая удочка
            has_rod = str(rod['id']) in user_data.get('rods', [])
            btn_text = f"{rod['emoji']} {rod['name']} - {rod['price']} руб"
            if has_rod:
                btn_text += " ✅"
            callback_data = f"buy_rod_{rod['id']}"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    rod_text = (
        f"🎣 *Купить удочку*\n\n"
        f"💰 Ваш баланс: {user_data['money']} руб\n\n"
        f"*Доступные удочки:*\n"
    )
    
    for rod_type, rods in rods_by_type.items():
        rod_text += f"\n*{rod_type.upper()}*:\n"
        for rod in rods:
            has_rod = str(rod['id']) in user_data.get('rods', [])
            status = "✅ Есть" if has_rod else "🛒 Купить"
            rod_text += f"\n{rod['emoji']} *{rod['name']}* - {rod['price']} руб {status}\n"
            rod_text += f"  🔧 Прочность: {rod['durability']} | 🍀 Удача: {rod['luck']}%\n"
            rod_text += f"  ⚖️ Макс. вес: {rod['max_weight']} кг | 💥 Шанс поломки: {rod['break_chance']}%\n"
    
    bot.send_message(message.chat.id, rod_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_rod_'))
def handle_buy_rod_callback(call):
    """Обработка покупки удочки"""
    user = call.from_user
    user_id_str = str(user.id)
    rod_id = call.data.split('_')[2]
    
    user_data = db.get_user(user.id)
    rod_info = next((r for r in RODS if str(r['id']) == rod_id), None)
    
    if not rod_info:
        bot.answer_callback_query(call.id, "❌ Удочка не найдена")
        return
    
    # Проверяем, есть ли уже такая удочка
    if str(rod_info['id']) in user_data.get('rods', []):
        bot.answer_callback_query(call.id, "❌ У вас уже есть эта удочка")
        return
    
    if user_data['money'] < rod_info['price']:
        bot.answer_callback_query(call.id, "❌ Недостаточно денег")
        return
    
    # Покупаем удочку
    user_data['money'] -= rod_info['price']
    db.add_rod(user.id, rod_id)
    
    # Логируем покупку
    db.add_log('buy_rod', user.id, f"{rod_info['name']} за {rod_info['price']} руб")
    
    response_text = (
        f"✅ *Покупка успешна!*\n\n"
        f"🎣 Куплено: {rod_info['emoji']} {rod_info['name']}\n"
        f"💰 Стоимость: {rod_info['price']} руб\n"
        f"💳 Осталось денег: {user_data['money']} руб\n\n"
        f"🔧 Прочность: {rod_info['durability']}\n"
        f"🍀 Удача: +{rod_info['luck']}%\n"
        f"⚖️ Макс. вес: {rod_info['max_weight']} кг\n\n"
        f"Теперь вы можете выбрать эту удочку в инвентаре!"
    )
    
    try:
        bot.edit_message_text(response_text, call.message.chat.id, call.message.message_id,
                            parse_mode='Markdown')
    except:
        bot.send_message(call.message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '🔧 Ремонт удочек')
def repair_rods_button_handler(message):
    """Ремонт удочек"""
    user = message.from_user
    user_data = db.get_user(user.id)
    
    # Создаем inline клавиатуру с удочками для ремонта
    markup = types.InlineKeyboardMarkup()
    
    repair_needed = False
    for rod_id in user_data.get('rods', []):
        rod_info = next((r for r in RODS if str(r['id']) == rod_id), None)
        if rod_info:
            current_durability = user_data['rod_durability'].get(rod_id, rod_info['durability'])
            max_durability = rod_info['durability']
            
            if current_durability < max_durability:
                repair_needed = True
                repair_cost = int((max_durability - current_durability) * 0.5)  # 0.5 руб за единицу прочности
                btn_text = f"{rod_info['emoji']} {rod_info['name']} - {repair_cost} руб"
                callback_data = f"repair_rod_{rod_id}"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    if not repair_needed:
        repair_text = "🔧 *Ремонт удочек*\n\n✅ Все ваши удочки в отличном состоянии! Ремонт не требуется."
        bot.send_message(message.chat.id, repair_text, parse_mode='Markdown',
                        reply_markup=create_shop_keyboard())
        return
    
    repair_text = (
        f"🔧 *Ремонт удочек*\n\n"
        f"💰 Ваш баланс: {user_data['money']} руб\n\n"
        f"*Удочки, требующие ремонта:*\n"
        f"Выберите удочку для полного восстановления прочности:"
    )
    
    bot.send_message(message.chat.id, repair_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('repair_rod_'))
def handle_repair_rod_callback(call):
    """Обработка ремонта удочки"""
    user = call.from_user
    user_id_str = str(user.id)
    rod_id = call.data.split('_')[2]
    
    user_data = db.get_user(user.id)
    rod_info = next((r for r in RODS if str(r['id']) == rod_id), None)
    
    if not rod_info:
        bot.answer_callback_query(call.id, "❌ Удочка не найдена")
        return
    
    # Проверяем, есть ли удочка
    if str(rod_info['id']) not in user_data.get('rods', []):
        bot.answer_callback_query(call.id, "❌ У вас нет этой удочки")
        return
    
    # Рассчитываем стоимость ремонта
    current_durability = user_data['rod_durability'].get(rod_id, rod_info['durability'])
    max_durability = rod_info['durability']
    
    if current_durability >= max_durability:
        bot.answer_callback_query(call.id, "✅ Удочка уже отремонтирована")
        return
    
    repair_cost = int((max_durability - current_durability) * 0.5)  # 0.5 руб за единицу прочности
    
    if user_data['money'] < repair_cost:
        bot.answer_callback_query(call.id, f"❌ Недостаточно денег. Нужно: {repair_cost} руб")
        return
    
    # Ремонтируем
    user_data['money'] -= repair_cost
    db.repair_rod(user.id, rod_id)
    
    # Логируем ремонт
    db.add_log('repair_rod', user.id, f"{rod_info['name']} за {repair_cost} руб")
    
    response_text = (
        f"🔧 *Удочка отремонтирована!*\n\n"
        f"🎣 Удочка: {rod_info['emoji']} {rod_info['name']}\n"
        f"💰 Стоимость ремонта: {repair_cost} руб\n"
        f"💳 Осталось денег: {user_data['money']} руб\n\n"
        f"✅ Прочность восстановлена до {rod_info['durability']}%"
    )
    
    try:
        bot.edit_message_text(response_text, call.message.chat.id, call.message.message_id,
                            parse_mode='Markdown')
    except:
        bot.send_message(call.message.chat.id, response_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '🏆 Топ игроков')
def top_button_handler(message):
    top_command(message)

@bot.message_handler(func=lambda msg: msg.text == '📰 Новости')
def news_button_handler(message):
    news_command(message)

@bot.message_handler(func=lambda msg: msg.text == '💰 Донат')
def donate_button_handler(message):
    # Создаем inline клавиатуру с пакетами доната
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for package in DONATE_PACKAGES:
        btn_text = f"{package['name']} - {package['price']} руб"
        callback_data = f"donate_package_{package['id']}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    donate_text = (
        f"💰 *Выберите пакет для доната*\n\n"
        f"💳 *Номер карты Тинькофф:*\n"
        f"`{TINKOFF_CARD}`\n\n"
        f"После перевода отправьте скриншот для получения награды."
    )
    
    bot.send_message(message.chat.id, donate_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('donate_package_'))
def handle_donate_package_callback(call):
    """Обработка выбора пакета доната"""
    package_id = int(call.data.split('_')[2])
    package = next((p for p in DONATE_PACKAGES if p['id'] == package_id), None)
    
    if not package:
        bot.answer_callback_query(call.id, "❌ Пакет не найден")
        return
    
    donate_text = (
        f"🎁 *Пакет: {package['name']}*\n\n"
        f"💰 Цена: {package['price']} руб\n"
    )
    
    if 'description' in package:
        donate_text += f"📝 Описание: {package['description']}\n\n"
    elif package['type'] == 'fishpop':
        donate_text += f"🎁 Награда: {package['amount']} рыбопоп\n\n"
    
    donate_text += f"💳 *Для оплаты:*\n"
    donate_text += f"1. Переведите *{package['price']} руб* на карту:\n"
    donate_text += f"`{TINKOFF_CARD}`\n\n"
    donate_text += f"2. Отправьте скриншот перевода в этот чат\n"
    donate_text += f"3. В описании укажите: \"Донат #{package_id}\"\n\n"
    donate_text += f"⏳ Награда будет выдана в течение 24 часов"
    
    # Создаем кнопку "Я оплатил"
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Я оплатил, отправить скриншот", 
                                         callback_data=f"confirm_payment_{package_id}"))
    
    try:
        bot.edit_message_text(donate_text, call.message.chat.id, call.message.message_id,
                            parse_mode='Markdown', reply_markup=markup)
    except:
        bot.send_message(call.message.chat.id, donate_text, parse_mode='Markdown', 
                        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_payment_'))
def handle_confirm_payment(call):
    """Подтверждение оплаты"""
    package_id = int(call.data.split('_')[2])
    package = next((p for p in DONATE_PACKAGES if p['id'] == package_id), None)
    
    if not package:
        bot.answer_callback_query(call.id, "❌ Пакет не найден")
        return
    
    bot.answer_callback_query(call.id, "📸 Теперь отправьте скриншот перевода")
    
    # Сохраняем информацию о ожидании скриншота
    user_id = call.from_user.id
    bot.send_message(
        call.message.chat.id,
        f"📸 *Ожидаю скриншот перевода*\n\n"
        f"Пакет: {package['name']}\n"
        f"Сумма: {package['price']} руб\n\n"
        f"Отправьте скриншот перевода в этот чат.\n"
        f"В подписи укажите: \"Донат #{package_id}\"\n\n"
        f"Для отмены напишите /cancel",
        parse_mode='Markdown'
    )

@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    """Обработка скриншотов доната"""
    user = message.from_user
    user_id_str = str(user.id)
    
    # Проверяем подпись
    caption = message.caption or ""
    
    # Ищем номер пакета в подписи
    package_match = re.search(r'#(\d+)', caption)
    if not package_match:
        bot.reply_to(message, "❌ В подписи укажите номер пакета: \"Донат #<номер>\"")
        return
    
    package_id = int(package_match.group(1))
    package = next((p for p in DONATE_PACKAGES if p['id'] == package_id), None)
    
    if not package:
        bot.reply_to(message, "❌ Пакет с таким номером не найден")
        return
    
    # Сохраняем транзакцию
    transaction = db.add_transaction(user.id, package_id, package['price'], 
                                    screenshot=message.photo[-1].file_id)
    
    # Пересылаем админам
    admin_message = (
        f"🤑 *Новый донат!*\n\n"
        f"👤 Пользователь: @{user.username or user.first_name} (ID: {user.id})\n"
        f"🎁 Пакет: {package['name']}\n"
        f"💰 Сумма: {package['price']} руб\n"
        f"📋 ID транзакции: {transaction['id']}\n\n"
        f"Для выдачи награды используйте команду:\n"
        f"/donate_complete {transaction['id']}"
    )
    
    # Отправляем всем админам для проверки чеков
    for admin_id in CHECK_ADMINS:
        try:
            # Пересылаем фото
            bot.send_photo(admin_id, message.photo[-1].file_id, 
                         caption=admin_message, parse_mode='Markdown')
        except Exception as e:
            print(f"Ошибка отправки админу {admin_id}: {e}")
    
    # Подтверждаем пользователю
    bot.reply_to(message,
                f"✅ *Скриншот получен!*\n\n"
                f"📋 ID транзакции: {transaction['id']}\n"
                f"⏳ Модераторы проверят перевод и выдадут награду в течение 24 часов.",
                parse_mode='Markdown')

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
def menu_button_handler(message):
    """Возврат в главное меню"""
    user = message.from_user
    user_id_str = str(user.id)
    
    # Проверяем уровень админа
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level > 0:
        bot.send_message(message.chat.id, "👑 Возвращаю в админ-меню:", 
                        reply_markup=create_admin_keyboard(admin_level))
    else:
        bot.send_message(message.chat.id, "📋 Возвращаю в главное меню:", 
                        reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '⬅️ Назад')
def back_button_handler(message):
    """Кнопка Назад"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level > 0:
        bot.send_message(message.chat.id, "👑 Админ панель", 
                        reply_markup=create_admin_keyboard(admin_level))
    else:
        bot.send_message(message.chat.id, "📋 Главное меню", 
                        reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '⬅️ В меню')
def back_to_menu_handler(message):
    """Возврат в меню для админов"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level > 0:
        bot.send_message(message.chat.id, "👑 Админ панель", 
                        reply_markup=create_admin_keyboard(admin_level))
    else:
        bot.send_message(message.chat.id, "📋 Главное меню", 
                        reply_markup=create_main_keyboard())

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(func=lambda msg: msg.text == '👑 Админ панель')
def admin_panel_handler(message):
    """Панель администратора"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level == 0:
        bot.reply_to(message, "❌ У вас нет прав администратора")
        return
    
    admin_text = (
        f"👑 *Панель администратора*\n\n"
        f"👤 Админ: {user.first_name}\n"
        f"📊 Уровень: {admin_level}\n"
        f"👥 Пользователей: {len(db.users)}\n"
        f"📰 Новостей: {len(db.news)}\n"
        f"💰 Транзакций: {len(db.transactions)}\n\n"
    )
    
    if admin_level >= 5:
        admin_text += "*Доступные команды:*\n"
        admin_text += "• Выдать награду\n"
        admin_text += "• Выдать предупреждение\n"
        admin_text += "• Забанить/разбанить\n"
        admin_text += "• Отправить новость\n"
        admin_text += "• Просмотр логов\n"
    
    bot.send_message(message.chat.id, admin_text, parse_mode='Markdown',
                    reply_markup=create_admin_keyboard(admin_level))

@bot.message_handler(func=lambda msg: msg.text == '📋 Список игроков')
def admin_players_list_handler(message):
    """Список игроков для админа"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level == 0:
        bot.reply_to(message, "❌ У вас нет прав администратора")
        return
    
    # Получаем всех игроков
    players = []
    for uid, user_data in db.users.items():
        players.append({
            'id': uid,
            'username': user_data.get('username', 'Неизвестно'),
            'first_name': user_data.get('first_name', 'Игрок'),
            'fish': user_data.get('total_fish', 0),
            'money': user_data.get('money', 0)
        })
    
    # Сортируем по количеству рыбы
    players = sorted(players, key=lambda x: x['fish'], reverse=True)
    
    # Разбиваем на страницы
    page_size = 10
    total_pages = (len(players) + page_size - 1) // page_size
    
    # Создаем inline клавиатуру для навигации
    markup = types.InlineKeyboardMarkup()
    if total_pages > 1:
        buttons = []
        if total_pages <= 5:
            for i in range(1, total_pages + 1):
                buttons.append(types.InlineKeyboardButton(str(i), callback_data=f"admin_page_{i}"))
        else:
            buttons.append(types.InlineKeyboardButton("1", callback_data="admin_page_1"))
            buttons.append(types.InlineKeyboardButton("...", callback_data="admin_page_more"))
            buttons.append(types.InlineKeyboardButton(str(total_pages), 
                                                     callback_data=f"admin_page_{total_pages}"))
        
        markup.row(*buttons)
    
    # Показываем первую страницу
    show_admin_players_page(message.chat.id, 1, players, page_size, markup)

def show_admin_players_page(chat_id, page_num, players, page_size, markup):
    """Показать страницу списка игроков"""
    start_idx = (page_num - 1) * page_size
    end_idx = start_idx + page_size
    page_players = players[start_idx:end_idx]
    
    players_text = f"📋 *Список игроков (страница {page_num})*\n\n"
    
    for i, player in enumerate(page_players, start_idx + 1):
        players_text += f"{i}. @{player['username']} ({player['first_name']})\n"
        players_text += f"   🆔: {player['id']}\n"
        players_text += f"   🐟 Рыбы: {player['fish']} | 💰 Деньги: {player['money']}\n\n"
    
    if not page_players:
        players_text = "📭 Пока нет зарегистрированных игроков"
    
    bot.send_message(chat_id, players_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_page_'))
def handle_admin_page_callback(call):
    """Обработка переключения страниц"""
    page_num = int(call.data.split('_')[2])
    # Здесь нужно перезагрузить данные и показать нужную страницу
    # Для упрощения просто закрываем callback
    bot.answer_callback_query(call.id, f"Страница {page_num}")

@bot.message_handler(func=lambda msg: msg.text == '⚡ Выдать награду')
def admin_give_reward_handler(message):
    """Выдача награды (для 5 лвл админов)"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 5:
        bot.reply_to(message, "❌ Недостаточно прав. Требуется уровень 5.")
        return
    
    # Запрашиваем ID пользователя
    msg = bot.send_message(message.chat.id,
                          "⚡ *Выдача награды*\n\n"
                          "Введите ID пользователя или @username:",
                          parse_mode='Markdown')
    
    bot.register_next_step_handler(msg, process_give_reward_user)

def process_give_reward_user(message):
    """Обработка ID пользователя для выдачи награды"""
    user_input = message.text.strip()
    
    # Ищем пользователя
    target_user = None
    
    if user_input.startswith('@'):
        # По username
        username = user_input[1:].lower()
        for uid, user_data in db.users.items():
            if user_data.get('username', '').lower() == username:
                target_user = uid
                break
    else:
        # По ID
        target_user = user_input
    
    if not target_user or target_user not in db.users:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    # Запрашиваем тип награды
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('💰 Деньги')
    btn2 = types.KeyboardButton('🪱 Наживка')
    btn3 = types.KeyboardButton('🎣 Удочка')
    btn4 = types.KeyboardButton('🏆 Рыбопоп')
    btn5 = types.KeyboardButton('🔧 Улучшение')
    btn6 = types.KeyboardButton('⬅️ Отмена')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    msg = bot.send_message(message.chat.id,
                          f"🎁 *Выдача награды пользователю*\n"
                          f"👤 ID: {target_user}\n\n"
                          f"Выберите тип награды:",
                          parse_mode='Markdown', reply_markup=markup)
    
    # Сохраняем ID пользователя для следующего шага
    bot.register_next_step_handler(msg, process_reward_type, target_user)

def process_reward_type(message, target_user_id):
    """Обработка типа награды"""
    reward_type = message.text
    
    if reward_type == '⬅️ Отмена':
        bot.send_message(message.chat.id, "❌ Отменено", 
                        reply_markup=create_admin_keyboard(5))
        return
    
    # Запрашиваем количество/ID
    if reward_type == '💰 Деньги':
        msg = bot.send_message(message.chat.id, "💵 Введите сумму денег:")
        bot.register_next_step_handler(msg, process_money_amount, target_user_id, message.from_user.id)
    elif reward_type == '🪱 Наживка':
        # Показываем список наживок
        markup = types.InlineKeyboardMarkup(row_width=2)
        for bait in BAITS:
            btn = types.InlineKeyboardButton(f"{bait['emoji']} {bait['name']}", 
                                           callback_data=f"admin_bait_{bait['id']}_{target_user_id}")
            markup.add(btn)
        
        bot.send_message(message.chat.id,
                        "🪱 Выберите наживку для выдачи:",
                        reply_markup=markup)
    elif reward_type == '🎣 Удочка':
        # Показываем список удочек
        markup = types.InlineKeyboardMarkup(row_width=2)
        for rod in RODS:
            if rod['price'] > 0:  # Платные удочки
                btn = types.InlineKeyboardButton(f"{rod['emoji']} {rod['name']}", 
                                               callback_data=f"admin_rod_{rod['id']}_{target_user_id}")
                markup.add(btn)
        
        bot.send_message(message.chat.id,
                        "🎣 Выберите удочку для выдачи:",
                        reply_markup=markup)
    elif reward_type == '🏆 Рыбопоп':
        msg = bot.send_message(message.chat.id, "🏆 Введите количество рыбопоп:")
        bot.register_next_step_handler(msg, process_fishpop_amount, target_user_id, message.from_user.id)
    elif reward_type == '🔧 Улучшение':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
        btn1 = types.KeyboardButton('🔧 Вечная удочка')
        btn2 = types.KeyboardButton('🍀 Удача +20%')
        btn3 = types.KeyboardButton('⬅️ Отмена')
        markup.add(btn1, btn2, btn3)
        
        msg = bot.send_message(message.chat.id,
                              "🔧 Выберите улучшение:",
                              reply_markup=markup)
        bot.register_next_step_handler(msg, process_upgrade_type, target_user_id)

def process_money_amount(message, target_user_id, admin_id):
    """Обработка суммы денег"""
    try:
        amount = int(message.text)
        if amount <= 0:
            bot.reply_to(message, "❌ Сумма должна быть положительной")
            return
        
        user_data = db.get_user(target_user_id)
        user_data['money'] += amount
        
        # Логируем действие
        db.add_log('admin_give_money', target_user_id, f"{amount} руб", admin_id)
        
        bot.reply_to(message,
                    f"✅ Успешно!\n\n"
                    f"💰 Пользователю {target_user_id} выдано: {amount} руб\n"
                    f"💳 Новый баланс: {user_data['money']} руб")
    
    except ValueError:
        bot.reply_to(message, "❌ Введите корректное число")

def process_fishpop_amount(message, target_user_id, admin_id):
    """Обработка количества рыбопоп"""
    try:
        amount = int(message.text)
        if amount <= 0:
            bot.reply_to(message, "❌ Количество должно быть положительным")
            return
        
        user_data = db.get_user(target_user_id)
        user_data['fishpop'] = user_data.get('fishpop', 0) + amount
        
        # Логируем действие
        db.add_log('admin_give_fishpop', target_user_id, f"{amount} рыбопоп", admin_id)
        
        bot.reply_to(message,
                    f"✅ Успешно!\n\n"
                    f"🏆 Пользователю {target_user_id} выдано: {amount} рыбопоп\n"
                    f"🎯 Теперь у него: {user_data['fishpop']} рыбопоп")
    
    except ValueError:
        bot.reply_to(message, "❌ Введите корректное число")

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_bait_'))
def handle_admin_give_bait(call):
    """Админ выдает наживку"""
    data_parts = call.data.split('_')
    bait_id = data_parts[2]
    target_user_id = data_parts[3]
    admin_id = call.from_user.id
    
    bait_info = next((b for b in BAITS if str(b['id']) == bait_id), None)
    if not bait_info:
        bot.answer_callback_query(call.id, "❌ Наживка не найдена")
        return
    
    # Выдаем наживку
    new_count = db.add_bait(target_user_id, bait_id, 1)
    
    # Логируем действие
    db.add_log('admin_give_bait', target_user_id, bait_info['name'], admin_id)
    
    response = (
        f"✅ Успешно!\n\n"
        f"🪱 Пользователю {target_user_id} выдано: {bait_info['name']}\n"
        f"📦 Теперь у него: {new_count} шт"
    )
    
    try:
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id)
    except:
        bot.send_message(call.message.chat.id, response)
    
    bot.answer_callback_query(call.id, "✅ Наживка выдана")

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_rod_'))
def handle_admin_give_rod(call):
    """Админ выдает удочку"""
    data_parts = call.data.split('_')
    rod_id = data_parts[2]
    target_user_id = data_parts[3]
    admin_id = call.from_user.id
    
    rod_info = next((r for r in RODS if str(r['id']) == rod_id), None)
    if not rod_info:
        bot.answer_callback_query(call.id, "❌ Удочка не найдена")
        return
    
    # Выдаем удочку
    db.add_rod(target_user_id, rod_id)
    
    # Логируем действие
    db.add_log('admin_give_rod', target_user_id, rod_info['name'], admin_id)
    
    response = (
        f"✅ Успешно!\n\n"
        f"🎣 Пользователю {target_user_id} выдано: {rod_info['name']}\n"
        f"🔧 Прочность: {rod_info['durability']}\n"
        f"🍀 Удача: +{rod_info['luck']}%"
    )
    
    try:
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id)
    except:
        bot.send_message(call.message.chat.id, response)
    
    bot.answer_callback_query(call.id, "✅ Удочка выдана")

def process_upgrade_type(message, target_user_id):
    """Обработка типа улучшения"""
    upgrade_type = message.text
    admin_id = message.from_user.id
    
    if upgrade_type == '⬅️ Отмена':
        bot.send_message(message.chat.id, "❌ Отменено", 
                        reply_markup=create_admin_keyboard(5))
        return
    
    user_data = db.get_user(target_user_id)
    
    if upgrade_type == '🔧 Вечная удочка':
        user_data['upgrades']['unbreakable'] = True
        upgrade_text = "Вечная удочка"
    elif upgrade_type == '🍀 Удача +20%':
        user_data['upgrades']['luck_boost'] = user_data['upgrades'].get('luck_boost', 0) + 20
        upgrade_text = "Удача +20%"
    else:
        bot.reply_to(message, "❌ Неизвестное улучшение")
        return
    
    db.save_data()
    
    # Логируем действие
    db.add_log('admin_give_upgrade', target_user_id, upgrade_text, admin_id)
    
    bot.reply_to(message,
                f"✅ Успешно!\n\n"
                f"🔧 Пользователю {target_user_id} выдано: {upgrade_text}\n"
                f"🎯 Теперь улучшения: {user_data['upgrades']}")

@bot.message_handler(func=lambda msg: msg.text == '⚠️ Выдать предупреждение')
def admin_warn_handler(message):
    """Выдача предупреждения"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 5:
        bot.reply_to(message, "❌ Недостаточно прав. Требуется уровень 5.")
        return
    
    msg = bot.send_message(message.chat.id,
                          "⚠️ *Выдача предупреждения*\n\n"
                          "Введите ID пользователя или @username:",
                          parse_mode='Markdown')
    
    bot.register_next_step_handler(msg, process_warn_user)

def process_warn_user(message):
    """Обработка выдачи предупреждения"""
    user_input = message.text.strip()
    admin_id = message.from_user.id
    
    # Ищем пользователя
    target_user = None
    
    if user_input.startswith('@'):
        username = user_input[1:].lower()
        for uid, user_data in db.users.items():
            if user_data.get('username', '').lower() == username:
                target_user = uid
                break
    else:
        target_user = user_input
    
    if not target_user or target_user not in db.users:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    # Выдаем предупреждение
    banned, warning_count, is_ban = db.add_warning(target_user)
    
    # Логируем действие
    db.add_log('admin_warn', target_user, f"Предупреждение {warning_count}/2", admin_id)
    
    response = f"⚠️ Пользователю {target_user} выдано предупреждение\n"
    response += f"📊 Всего предупреждений: {warning_count}/2\n"
    
    if is_ban:
        response += f"\n🚫 Пользователь забанен на 2 дня!"
    
    bot.reply_to(message, response)

@bot.message_handler(func=lambda msg: msg.text == '🚫 Забанить')
def admin_ban_handler(message):
    """Бан пользователя"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 5:
        bot.reply_to(message, "❌ Недостаточно прав. Требуется уровень 5.")
        return
    
    msg = bot.send_message(message.chat.id,
                          "🚫 *Бан пользователя*\n\n"
                          "Введите ID пользователя или @username:",
                          parse_mode='Markdown')
    
    bot.register_next_step_handler(msg, process_ban_user)

def process_ban_user(message):
    """Обработка бана пользователя"""
    user_input = message.text.strip()
    admin_id = message.from_user.id
    
    # Ищем пользователя
    target_user = None
    
    if user_input.startswith('@'):
        username = user_input[1:].lower()
        for uid, user_data in db.users.items():
            if user_data.get('username', '').lower() == username:
                target_user = uid
                break
    else:
        target_user = user_input
    
    if not target_user or target_user not in db.users:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    # Баним
    user_data = db.get_user(target_user)
    user_data['banned_until'] = time.time() + BAN_DURATION
    db.save_data()
    
    # Логируем действие
    db.add_log('admin_ban', target_user, "Бан на 2 дня", admin_id)
    
    bot.reply_to(message,
                f"🚫 Пользователь {target_user} забанен на 2 дня!\n"
                f"⏳ Бан истечет: {datetime.fromtimestamp(user_data['banned_until']).strftime('%d.%m.%Y %H:%M')}")

@bot.message_handler(func=lambda msg: msg.text == '✅ Снять бан')
def admin_unban_handler(message):
    """Снятие бана"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 5:
        bot.reply_to(message, "❌ Недостаточно прав. Требуется уровень 5.")
        return
    
    msg = bot.send_message(message.chat.id,
                          "✅ *Снятие бана*\n\n"
                          "Введите ID пользователя или @username:",
                          parse_mode='Markdown')
    
    bot.register_next_step_handler(msg, process_unban_user)

def process_unban_user(message):
    """Обработка снятия бана"""
    user_input = message.text.strip()
    admin_id = message.from_user.id
    
    # Ищем пользователя
    target_user = None
    
    if user_input.startswith('@'):
        username = user_input[1:].lower()
        for uid, user_data in db.users.items():
            if user_data.get('username', '').lower() == username:
                target_user = uid
                break
    else:
        target_user = user_input
    
    if not target_user or target_user not in db.users:
        bot.reply_to(message, "❌ Пользователь не найден")
        return
    
    # Снимаем бан
    user_data = db.get_user(target_user)
    user_data['banned_until'] = None
    db.save_data()
    
    # Логируем действие
    db.add_log('admin_unban', target_user, "Снятие бана", admin_id)
    
    bot.reply_to(message, f"✅ Бан с пользователя {target_user} снят!")

@bot.message_handler(func=lambda msg: msg.text == '📢 Отправить новость')
def admin_news_handler(message):
    """Отправка новости"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 5:
        bot.reply_to(message, "❌ Недостаточно прав. Требуется уровень 5.")
        return
    
    msg = bot.send_message(message.chat.id,
                          "📢 *Отправка новости*\n\n"
                          "Введите текст новости:",
                          parse_mode='Markdown')
    
    bot.register_next_step_handler(msg, process_news_text)

def process_news_text(message):
    """Обработка текста новости"""
    news_text = message.text.strip()
    admin_id = message.from_user.id
    
    if not news_text:
        bot.reply_to(message, "❌ Текст новости не может быть пустым")
        return
    
    # Добавляем новость
    news_entry = db.add_news(news_text, admin_id)
    
    # Отправляем всем пользователям
    sent_count = 0
    for user_id in db.users:
        try:
            news_message = (
                f"📰 *Новая новость!*\n\n"
                f"{news_text}\n\n"
                f"📅 {datetime.fromtimestamp(news_entry['timestamp']).strftime('%d.%m.%Y %H:%M')}"
            )
            bot.send_message(user_id, news_message, parse_mode='Markdown')
            sent_count += 1
        except:
            pass  # Пользователь заблокировал бота
    
    # Логируем действие
    db.add_log('admin_news', 'all', f"Новость: {news_text[:50]}...", admin_id)
    
    bot.reply_to(message,
                f"✅ Новость отправлена!\n\n"
                f"📊 Получили: {sent_count}/{len(db.users)} пользователей\n"
                f"📅 Дата: {datetime.fromtimestamp(news_entry['timestamp']).strftime('%d.%m.%Y %H:%M')}")

@bot.message_handler(func=lambda msg: msg.text == '📊 Логи действий')
def admin_logs_handler(message):
    """Просмотр логов"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 5:
        bot.reply_to(message, "❌ Недостаточно прав. Требуется уровень 5.")
        return
    
    # Получаем последние 20 логов
    recent_logs = db.logs[-20:] if len(db.logs) > 20 else db.logs
    
    if not recent_logs:
        bot.reply_to(message, "📭 Логов пока нет")
        return
    
    logs_text = "📊 *Последние действия*\n\n"
    
    for log in reversed(recent_logs):
        date = datetime.fromtimestamp(log['timestamp']).strftime("%d.%m %H:%M")
        action = log['action']
        user_id = log['user_id']
        details = log['details'][:50]
        
        logs_text += f"📅 {date} | 👤 {user_id}\n"
        logs_text += f"📝 {action}: {details}\n"
        
        if log.get('admin_id'):
            logs_text += f"👑 Админ: {log['admin_id']}\n"
        
        logs_text += "─" * 30 + "\n"
    
    bot.send_message(message.chat.id, logs_text, parse_mode='Markdown')

# ========== КОМАНДЫ ДЛЯ ОБРАБОТКИ ДОНАТА (для админов 1 лвл) ==========
@bot.message_handler(commands=['donate_complete'])
def donate_complete_command(message):
    """Завершение транзакции доната (для админов)"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 1:
        bot.reply_to(message, "❌ Недостаточно прав. Требуется уровень админа.")
        return
    
    # Получаем ID транзакции
    try:
        transaction_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, "❌ Использование: /donate_complete <ID_транзакции>")
        return
    
    # Ищем транзакцию
    transaction = None
    for t in db.transactions:
        if t['id'] == transaction_id and t['status'] == 'pending':
            transaction = t
            break
    
    if not transaction:
        bot.reply_to(message, "❌ Транзакция не найдена или уже обработана")
        return
    
    # Завершаем транзакцию
    if db.complete_transaction(transaction_id, user.id):
        # Выдаем награду пользователю
        package = next((p for p in DONATE_PACKAGES if p['id'] == transaction['package_id']), None)
        if not package:
            bot.reply_to(message, "❌ Пакет не найден")
            return
        
        target_user_id = transaction['user_id']
        user_data = db.get_user(target_user_id)
        
        # Выдаем награду в зависимости от типа пакета
        if package['type'] == 'upgrade':
            if package['id'] == 1:  # Вечная удочка
                user_data['upgrades']['unbreakable'] = True
                reward_text = "🔧 Вечная удочка"
            else:
                bot.reply_to(message, f"❌ Неизвестное улучшение: {package['name']}")
                return
                
        elif package['type'] == 'luck':
            user_data['upgrades']['luck_boost'] = user_data['upgrades'].get('luck_boost', 0) + 20
            reward_text = "🍀 Удача +20%"
            
        elif package['type'] == 'rod':
            # Добавляем спиннинг с удачей 30%
            rod_id = 4  # Спиннинг Shimano Catana
            db.add_rod(target_user_id, rod_id)
            rod_info = next((r for r in RODS if r['id'] == rod_id), None)
            reward_text = f"🎣 {rod_info['name']} с удачей 30%"
            
        elif package['type'] == 'fishpop':
            user_data['fishpop'] = user_data.get('fishpop', 0) + package['amount']
            reward_text = f"🏆 {package['amount']} рыбопоп"
            
        else:
            bot.reply_to(message, f"❌ Неизвестный тип пакета: {package['type']}")
            return
        
        db.save_data()
        
        # Логируем
        db.add_log('donate_complete', target_user_id, 
                  f"{package['name']} за {package['price']} руб", user.id)
        
        # Уведомляем админа
        bot.reply_to(message,
                    f"✅ *Транзакция завершена!*\n\n"
                    f"👤 Пользователь: {target_user_id}\n"
                    f"🎁 Пакет: {package['name']}\n"
                    f"💰 Сумма: {package['price']} руб\n"
                    f"🎁 Выдано: {reward_text}")
        
        # Уведомляем пользователя
        try:
            bot.send_message(target_user_id,
                           f"🎉 *Спасибо за донат!*\n\n"
                           f"✅ Ваш пакет активирован!\n"
                           f"🎁 Получено: {reward_text}\n\n"
                           f"Приятной игры! 🎣")
        except:
            pass  # Пользователь заблокировал бота
        
    else:
        bot.reply_to(message, "❌ Ошибка при завершении транзакции")

@bot.message_handler(commands=['donate_list'])
def donate_list_command(message):
    """Список ожидающих транзакций"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 1:
        bot.reply_to(message, "❌ Недостаточно прав. Требуется уровень админа.")
        return
    
    pending_transactions = [t for t in db.transactions if t['status'] == 'pending']
    
    if not pending_transactions:
        bot.reply_to(message, "✅ Нет ожидающих транзакций")
        return
    
    transactions_text = "📋 *Ожидающие транзакции*\n\n"
    
    for t in pending_transactions[-10:]:  # Последние 10
        package = next((p for p in DONATE_PACKAGES if p['id'] == t['package_id']), None)
        date = datetime.fromtimestamp(t['timestamp']).strftime("%d.%m %H:%M")
        
        transactions_text += f"📋 *ID:* {t['id']}\n"
        transactions_text += f"👤 Пользователь: {t['user_id']}\n"
        transactions_text += f"🎁 Пакет: {package['name'] if package else 'Неизвестно'}\n"
        transactions_text += f"💰 Сумма: {t['amount']} руб\n"
        transactions_text += f"📅 Дата: {date}\n"
        transactions_text += f"✅ Для выдачи: /donate_complete {t['id']}\n"
        transactions_text += "─" * 30 + "\n\n"
    
    bot.reply_to(message, transactions_text, parse_mode='Markdown')

# ========== WEBHOOK РОУТЫ ==========
@app.route(f'/{BOT_TOKEN}', methods=['POST'])
def webhook():
    """Основной endpoint для получения обновлений от Telegram"""
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'ok', 200
    return 'error', 403

@app.route('/')
def home():
    return "🎣 Fishing Bot Extended is running! Use /set_webhook to configure", 200

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка webhook"""
    if not WEBHOOK_URL:
        return "❌ RENDER_EXTERNAL_URL не настроен", 500
    
    try:
        bot.remove_webhook()
        time.sleep(0.1)
        
        s = bot.set_webhook(
            url=WEBHOOK_URL,
            max_connections=50,
            allowed_updates=["message", "callback_query", "inline_query"]
        )
        
        if s:
            return f"✅ Webhook установлен!\nURL: {WEBHOOK_URL}", 200
        else:
            return "❌ Ошибка установки webhook", 500
    except Exception as e:
        return f"❌ Ошибка: {str(e)}", 500

@app.route('/remove_webhook', methods=['GET'])
def remove_webhook():
    """Удаление webhook"""
    try:
        bot.remove_webhook()
        return "✅ Webhook удален", 200
    except Exception as e:
        return f"❌ Ошибка: {str(e)}", 500

@app.route('/health')
def health():
    """Эндпоинт для проверки здоровья"""
    return "OK", 200

@app.route('/status')
def status():
    """Статус бота"""
    try:
        bot_info = bot.get_me()
        return json.dumps({
            "status": "running",
            "bot": f"@{bot_info.username}",
            "webhook": WEBHOOK_URL,
            "users_count": len(db.users),
            "transactions_pending": len([t for t in db.transactions if t['status'] == 'pending']),
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

# ========== ОБРАБОТКА ВСЕХ СООБЩЕНИЙ ==========
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_messages(message):
    delete_links_in_group(message)
    
    text = message.text
    if text in ['🎣 Начать рыбалку', '📍 Сменить водоем', '🛒 Магазин', '📊 Статистика',
                '🎒 Инвентарь', '🏆 Топ игроков', '📰 Новости', '💰 Донат', '❓ Помощь',
                '🎣 Забросить удочку', '📋 Меню', '⬅️ Назад', '⬅️ В меню',
                '👑 Админ панель', '📋 Список игроков', '⚡ Выдать награду',
                '⚠️ Выдать предупреждение', '🚫 Забанить', '✅ Снять бан',
                '📢 Отправить новость', '📊 Логи действий']:
        return
    if text and text.startswith('/'):
        return

@bot.message_handler(content_types=['photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle_media_messages(message):
    delete_links_in_group(message)

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
if __name__ == '__main__':
    print("=" * 50)
    print("🎣 Fishing Bot Extended Edition")
    print(f"✅ Webhook URL: {WEBHOOK_URL if WEBHOOK_URL else 'Не настроен'}")
    print("=" * 50)
    
    try:
        bot_info = bot.get_me()
        print(f"✅ Бот загружен: @{bot_info.username} ({bot_info.first_name})")
    except Exception as e:
        print(f"❌ Ошибка загрузки бота: {e}")
    
    # Запускаем keep-alive сервис
    if RENDER_URL:
        keeper = KeepAliveService(RENDER_URL)
        keeper.start()
        print("✅ Keep-alive service started")
    else:
        print("⚠️ Keep-alive отключен (не настроен RENDER_EXTERNAL_URL)")
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Запуск Flask на порту {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
