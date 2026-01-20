#!/usr/bin/env python3
# bot.py - Полный бот с keep-alive для Render
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
        
    def stop(self):
        """Останавливаем keep-alive"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            
    def _ping_loop(self):
        """Основной цикл пингов"""
        ping_count = 0
        
        # Первый пинг сразу при старте
        self._send_ping()
        ping_count += 1
        
        while self.running:
            try:
                # Ждем указанный интервал
                time.sleep(self.ping_interval)
                
                if self.running:
                    self._send_ping()
                    ping_count += 1
                    
                    # Логируем каждые 10 пингов
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

# Получаем URL от Render
RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
WEBHOOK_URL = f'{RENDER_URL}/{BOT_TOKEN}' if RENDER_URL else None

# Настройки игры (БЕЗ ИЗМЕНЕНИЙ!)
INITIAL_WORMS = 10
MAX_WORMS = 10
FISHING_TIME = 30
WORM_REFILL_TIME = 900  # 15 минут
WARNING_EXPIRE_TIME = 86400  # 24 часа
BAN_DURATION = 172800  # 2 дня

# Монеты и магазин
COINS_NAME = "рыбоп"
INITIAL_COINS = 100
WORM_PRICE = 10

# Админ система
ADMINS = {
    "5330661807": 5  # 5 уровень - полный доступ
}
ADMIN_LOG_FILE = 'admin_logs.json'
ACTION_LOG_FILE = 'action_logs.json'

# ========== РЫБЫ РОССИИ (30 видов) ==========
FISHES = [
    {"name": "🐟 Щука", "rarity": "обычная", "weight": "1-5кг", "emoji": "🐟", "price": 50, "baits": ["червь", "мотыль", "опарыш", "мелкая рыба"]},
    {"name": "🐟 Окунь", "rarity": "обычная", "weight": "200-500г", "emoji": "🐟", "price": 30, "baits": ["червь", "мотыль", "опарыш"]},
    {"name": "🐟 Карась", "rarity": "обычная", "weight": "300-700г", "emoji": "🐟", "price": 25, "baits": ["червь", "мотыль", "опарыш", "перловка"]},
    {"name": "🐟 Лещ", "rarity": "обычная", "weight": "1-3кг", "emoji": "🐟", "price": 40, "baits": ["червь", "мотыль", "опарыш", "горох"]},
    {"name": "🐟 Плотва", "rarity": "обычная", "weight": "150-400г", "emoji": "🐟", "price": 20, "baits": ["червь", "мотыль", "опарыш"]},
    {"name": "🐟 Судак", "rarity": "редкая", "weight": "2-6кг", "emoji": "🐠", "price": 100, "baits": ["мелкая рыба", "червь", "твистер"]},
    {"name": "🐟 Сом", "rarity": "эпическая", "weight": "5-20кг", "emoji": "🐠", "price": 300, "baits": ["лягушка", "мелкая рыба", "червь", "рак"]},
    {"name": "🐟 Карп", "rarity": "редкая", "weight": "2-8кг", "emoji": "🐟", "price": 150, "baits": ["кукуруза", "червь", "горох", "бойлы"]},
    {"name": "🐟 Сазан", "rarity": "редкая", "weight": "3-12кг", "emoji": "🐟", "price": 180, "baits": ["кукуруза", "червь", "горох", "бойлы"]},
    {"name": "🐟 Форель", "rarity": "редкая", "weight": "1-3кг", "emoji": "🐠", "price": 120, "baits": ["червь", "мотыль", "опарыш", "икра"]},
    {"name": "🐟 Голавль", "rarity": "обычная", "weight": "500г-2кг", "emoji": "🐟", "price": 60, "baits": ["кузнечик", "червь", "мотыль"]},
    {"name": "🐟 Жерех", "rarity": "редкая", "weight": "2-5кг", "emoji": "🐟", "price": 110, "baits": ["мелкая рыба", "блесна", "воблер"]},
    {"name": "🐟 Язь", "rarity": "редкая", "weight": "1-3кг", "emoji": "🐟", "price": 90, "baits": ["червь", "мотыль", "кузнечик"]},
    {"name": "🐟 Красноперка", "rarity": "обычная", "weight": "100-300г", "emoji": "🐟", "price": 15, "baits": ["червь", "мотыль", "опарыш"]},
    {"name": "🐟 Линь", "rarity": "редкая", "weight": "1-4кг", "emoji": "🐟", "price": 130, "baits": ["червь", "мотыль", "опарыш"]},
    {"name": "🐟 Налим", "rarity": "редкая", "weight": "1-5кг", "emoji": "🐟", "price": 140, "baits": ["червь", "мелкая рыба", "куски рыбы"]},
    {"name": "🐟 Осетр", "rarity": "легендарная", "weight": "10-30кг", "emoji": "🐠", "price": 1000, "baits": ["червь", "мелкая рыба", "рак"]},
    {"name": "🐟 Белуга", "rarity": "легендарная", "weight": "50-100кг", "emoji": "🐳", "price": 5000, "baits": ["мелкая рыба", "червь", "рак"]},
    {"name": "🐟 Стерлядь", "rarity": "эпическая", "weight": "2-5кг", "emoji": "🐟", "price": 800, "baits": ["червь", "мотыль", "опарыш"]},
    {"name": "🦞 Рак", "rarity": "обычная", "weight": "50-150г", "emoji": "🦞", "price": 40, "baits": ["червь", "рыба", "мясо"]},
    {"name": "🦐 Креветка", "rarity": "обычная", "weight": "20-50г", "emoji": "🦐", "price": 10, "baits": ["хлеб", "червь", "мотыль"]},
    {"name": "🦀 Краб", "rarity": "редкая", "weight": "300г-1кг", "emoji": "🦀", "price": 150, "baits": ["рыба", "мясо", "червь"]},
    {"name": "🐙 Кальмар", "rarity": "редкая", "weight": "1-3кг", "emoji": "🐙", "price": 200, "baits": ["мелкая рыба", "червь", "креветка"]},
    {"name": "🐡 Фугу", "rarity": "эпическая", "weight": "1-2кг", "emoji": "🐡", "price": 600, "baits": ["червь", "креветка", "мелкая рыба"]},
    {"name": "🎣 Ботинок", "rarity": "мусор", "weight": "1-2кг", "emoji": "🎣", "price": 1, "baits": []},
    {"name": "🗑️ Пакет", "rarity": "мусор", "weight": "200г", "emoji": "🗑️", "price": 1, "baits": []},
    {"name": "🍺 Банка", "rarity": "мусор", "weight": "500г", "emoji": "🍺", "price": 1, "baits": []},
    {"name": "👑 Золотая рыбка", "rarity": "легендарная", "weight": "100г", "emoji": "👑", "price": 10000, "baits": ["червь", "мотыль", "хлеб"]},
    {"name": "🎏 Золотая рыбка (декоративная)", "rarity": "эпическая", "weight": "300г", "emoji": "🎏", "price": 2000, "baits": ["спецкорм", "червь"]},
    {"name": "🌿 Водоросли", "rarity": "мусор", "weight": "100-300г", "emoji": "🌿", "price": 1, "baits": []}
]

# ========== ЧЕРВЯКИ И НАЖИВКИ (30 видов) ==========
BAITS = [
    {"name": "🌱 Обычный червь", "price": 10, "emoji": "🌱", "description": "Базовый червь для большинства рыб", "effectiveness": 1.0},
    {"name": "🔴 Мотыль", "price": 15, "emoji": "🔴", "description": "Личинка комара, хорош для зимней рыбалки", "effectiveness": 1.2},
    {"name": "⚪ Опарыш", "price": 20, "emoji": "⚪", "description": "Личинка мухи, привлекает крупную рыбу", "effectiveness": 1.3},
    {"name": "🟡 Навозный червь", "price": 25, "emoji": "🟡", "description": "Крупный червь с сильным запахом", "effectiveness": 1.4},
    {"name": "🌽 Кукуруза", "price": 30, "emoji": "🌽", "description": "Любимая приманка карпа и сазана", "effectiveness": 1.5},
    {"name": "🟢 Горох", "price": 35, "emoji": "🟢", "description": "Отличная приманка для леща", "effectiveness": 1.4},
    {"name": "🍞 Хлеб", "price": 5, "emoji": "🍞", "description": "Бюджетная приманка для мелкой рыбы", "effectiveness": 0.8},
    {"name": "🐛 Червь-выползок", "price": 50, "emoji": "🐛", "description": "Крупный червь для хищной рыбы", "effectiveness": 1.7},
    {"name": "🦗 Кузнечик", "price": 40, "emoji": "🦗", "description": "Натуральная приманка для голавля", "effectiveness": 1.6},
    {"name": "🐸 Лягушка", "price": 100, "emoji": "🐸", "description": "Лучшая приманка для сома", "effectiveness": 2.0},
    {"name": "🦐 Креветка", "price": 60, "emoji": "🦐", "description": "Морская приманка для хищников", "effectiveness": 1.8},
    {"name": "🐟 Мелкая рыба", "price": 80, "emoji": "🐟", "description": "Живец для щуки и судака", "effectiveness": 2.0},
    {"name": "🥚 Икра", "price": 150, "emoji": "🥚", "description": "Дорогая приманка для форели", "effectiveness": 2.2},
    {"name": "🥩 Мясо", "price": 70, "emoji": "🥩", "description": "Приманка для раков и крабов", "effectiveness": 1.5},
    {"name": "🍖 Сальник", "price": 45, "emoji": "🍖", "description": "Личинка майского жука", "effectiveness": 1.6},
    {"name": "🦪 Мидия", "price": 55, "emoji": "🦪", "description": "Моллюск для морской рыбалки", "effectiveness": 1.7},
    {"name": "🐌 Улитка", "price": 35, "emoji": "🐌", "description": "Натуральная приманка для карпа", "effectiveness": 1.4},
    {"name": "🧀 Сыр", "price": 65, "emoji": "🧀", "description": "Ароматная приманка", "effectiveness": 1.5},
    {"name": "🍯 Тесто", "price": 25, "emoji": "🍯", "description": "Домашняя приманка", "effectiveness": 1.2},
    {"name": "🎣 Бойлы", "price": 200, "emoji": "🎣", "description": "Профессиональная приманка для карпа", "effectiveness": 2.5},
    {"name": "🎣 Твистер", "price": 120, "emoji": "🎣", "description": "Силиконовая приманка", "effectiveness": 1.8},
    {"name": "🎣 Воблер", "price": 300, "emoji": "🎣", "description": "Дорогая искусственная приманка", "effectiveness": 2.0},
    {"name": "🎣 Блесна", "price": 180, "emoji": "🎣", "description": "Металлическая приманка", "effectiveness": 1.9},
    {"name": "💎 Перловка", "price": 20, "emoji": "💎", "description": "Дешевая растительная приманка", "effectiveness": 1.1},
    {"name": "🌾 Пшеница", "price": 15, "emoji": "🌾", "description": "Зерновая приманка", "effectiveness": 1.0},
    {"name": "🥜 Арахис", "price": 90, "emoji": "🥜", "description": "Ароматная приманка", "effectiveness": 1.7},
    {"name": "🧅 Чеснок", "price": 40, "emoji": "🧅", "description": "Ароматизатор для приманки", "effectiveness": 1.3},
    {"name": "🍯 Мед", "price": 110, "emoji": "🍯", "description": "Сладкая добавка к приманке", "effectiveness": 1.6},
    {"name": "🌿 Анис", "price": 85, "emoji": "🌿", "description": "Ароматическая приманка", "effectiveness": 1.5},
    {"name": "⭐ Спецкорм", "price": 500, "emoji": "⭐", "description": "Элитная приманка для редкой рыбы", "effectiveness": 3.0}
]

# ========== УДОЧКИ ==========
RODS = [
    {"name": "🎣 Простая удочка", "price": 100, "emoji": "🎣", "description": "Базовая удочка для начинающих", "power": 1.0, "durability": 100},
    {"name": "🎣 Удочка новичка", "price": 500, "emoji": "🎣", "description": "Улучшенная удочка", "power": 1.2, "durability": 150},
    {"name": "🎣 Профессиональная удочка", "price": 2000, "emoji": "🎣", "description": "Для опытных рыбаков", "power": 1.5, "durability": 200},
    {"name": "🎣 Карповая удочка", "price": 5000, "emoji": "🎣", "description": "Специальная удочка для карпа", "power": 1.8, "durability": 250},
    {"name": "🎣 Спиннинг", "price": 3000, "emoji": "🎣", "description": "Для ловли хищной рыбы", "power": 2.0, "durability": 180},
    {"name": "🎣 Фидер", "price": 4000, "emoji": "🎣", "description": "Для донной ловли", "power": 1.7, "durability": 220},
    {"name": "🎣 Матчевая удочка", "price": 3500, "emoji": "🎣", "description": "Для дальних забросов", "power": 1.6, "durability": 200},
    {"name": "🎣 Нахлыстовая удочка", "price": 6000, "emoji": "🎣", "description": "Для искусственных мушек", "power": 2.2, "durability": 170},
    {"name": "🎣 Морская удочка", "price": 8000, "emoji": "🎣", "description": "Для морской рыбалки", "power": 2.5, "durability": 300},
    {"name": "🏆 Легендарная удочка", "price": 20000, "emoji": "🏆", "description": "Элитная удочка мастера", "power": 3.0, "durability": 500}
]

# ========== ЕЖЕДНЕВНЫЕ ЗАДАНИЯ ==========
DAILY_QUESTS = [
    {"id": 1, "name": "🎣 Начинающий рыбак", "description": "Поймайте 5 любых рыб", "reward": 100, "type": "catch", "target": 5},
    {"id": 2, "name": "💰 Продавец рыбы", "description": "Продайте рыбу на 300 рыбоп", "reward": 150, "type": "sell", "target": 300},
    {"id": 3, "name": "🛒 Покупатель", "description": "Купите 3 червяка в магазине", "reward": 80, "type": "buy_bait", "target": 3},
    {"id": 4, "name": "🐟 Охотник за редкой рыбой", "description": "Поймайте 2 редкие рыбы", "reward": 200, "type": "catch_rare", "target": 2},
    {"id": 5, "name": "🌟 Коллекционер", "description": "Поймайте 1 эпическую рыбу", "reward": 500, "type": "catch_epic", "target": 1},
    {"id": 6, "name": "👑 Мастер рыбалки", "description": "Поймайте 1 легендарную рыбу", "reward": 1000, "type": "catch_legendary", "target": 1},
    {"id": 7, "name": "🎣 Улучшение снастей", "description": "Купите новую удочку", "reward": 300, "type": "buy_rod", "target": 1},
    {"id": 8, "name": "💪 Трудяга", "description": "Заработайте 500 рыбоп за день", "reward": 250, "type": "earn", "target": 500},
    {"id": 9, "name": "🔄 Многостаночник", "description": "Выполните 3 разных задания", "reward": 400, "type": "complete_quests", "target": 3},
    {"id": 10, "name": "🏆 Чемпион дня", "description": "Займите 1 место в топе", "reward": 1000, "type": "top_1", "target": 1}
]

# ========== НПС ДЛЯ ПРОДАЖИ ==========
NPC_SELLERS = [
    {"name": "👨‍🌾 Рыбный торговец", "emoji": "👨‍🌾", "multiplier": 1.0, "description": "Покупает рыбу по обычной цене"},
    {"name": "👨‍🍳 Ресторатор", "emoji": "👨‍🍳", "multiplier": 1.2, "description": "Платит на 20% больше за свежую рыбу"},
    {"name": "👨‍🔬 Ученый", "emoji": "👨‍🔬", "multiplier": 1.5, "description": "Покупает редкую рыбу для исследований"},
    {"name": "👑 Коллекционер", "emoji": "👑", "multiplier": 2.0, "description": "Платит вдвое больше за легендарную рыбу"}
]

# Редкости и их вероятности - БЕЗ ИЗМЕНЕНИЙ!
RARITY_PROBABILITIES = {
    "обычная": 50,
    "редкая": 30,
    "эпическая": 15,
    "легендарная": 4,
    "мусор": 1
}

# Регулярные выражения - БЕЗ ИЗМЕНЕНИЙ!
URL_PATTERN = re.compile(
    r'(https?://[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9-]+\.(com|ru|net|org|info|io|me|tv|co|us|uk|de|fr|es|it|jp|cn|рф)[^\s]*)|(t\.me/[^\s]+)|(telegram\.me/[^\s]+)|(tg://[^\s]+)'
)
USERNAME_PATTERN = re.compile(r'@[a-zA-Z0-9_]{5,32}')

# ========== USER DATABASE (РАСШИРЕННАЯ) ==========
class UserDatabase:
    def __init__(self):
        self.users = {}
        self.active_fishing = {}
        self.admin_logs = []
        self.action_logs = []
        self.load_data()
        self.load_logs()
    
    def load_data(self):
        """Загружаем данные из файла (если есть)"""
        try:
            with open('users_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.users = data.get('users', {})
                ADMINS.update(data.get('admins', {}))
            print(f"✅ Загружено {len(self.users)} пользователей")
        except FileNotFoundError:
            print("📁 Файл данных не найден, начинаем с чистого листа")
            self.users = {}
        except Exception as e:
            print(f"⚠️ Ошибка загрузки данных: {e}")
            self.users = {}
    
    def load_logs(self):
        """Загружаем логи"""
        try:
            with open(ADMIN_LOG_FILE, 'r', encoding='utf-8') as f:
                self.admin_logs = json.load(f)
            print(f"✅ Загружено {len(self.admin_logs)} логов админов")
        except FileNotFoundError:
            self.admin_logs = []
        
        try:
            with open(ACTION_LOG_FILE, 'r', encoding='utf-8') as f:
                self.action_logs = json.load(f)
            print(f"✅ Загружено {len(self.action_logs)} логов действий")
        except FileNotFoundError:
            self.action_logs = []
    
    def save_data(self):
        """Сохраняем данные в файл"""
        try:
            data = {
                'users': self.users,
                'admins': ADMINS
            }
            with open('users_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("💾 Данные сохранены")
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    
    def save_logs(self):
        """Сохраняем логи"""
        try:
            with open(ADMIN_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.admin_logs, f, ensure_ascii=False, indent=2)
            
            with open(ACTION_LOG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.action_logs, f, ensure_ascii=False, indent=2)
            print("💾 Логи сохранены")
        except Exception as e:
            print(f"❌ Ошибка сохранения логов: {e}")
    
    def log_admin_action(self, admin_id, action, target_id=None, details=""):
        """Логируем действие админа"""
        log_entry = {
            "admin_id": str(admin_id),
            "action": action,
            "target_id": str(target_id) if target_id else None,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.admin_logs.append(log_entry)
        if len(self.admin_logs) > 1000:
            self.admin_logs = self.admin_logs[-1000:]
        self.save_logs()
    
    def log_action(self, user_id, action_type, details=""):
        """Логируем действие пользователя"""
        log_entry = {
            "user_id": str(user_id),
            "action_type": action_type,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.action_logs.append(log_entry)
        if len(self.action_logs) > 5000:
            self.action_logs = self.action_logs[-5000:]
        self.save_logs()
    
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
                'banned_until': None,
                'coins': INITIAL_COINS,
                'inventory': {
                    'rods': [{"name": "🎣 Простая удочка", "equipped": True}],
                    'baits': [{"name": "🌱 Обычный червь", "count": 10}],
                    'fish': {}
                },
                'daily_quests': {},
                'quests_completed_today': 0,
                'last_daily_reset': datetime.now().isoformat(),
                'current_rod': "🎣 Простая удочка",
                'current_bait': "🌱 Обычный червь",
                'favorite_fishing_spots': [],
                'achievements': [],
                'fishing_level': 1,
                'experience': 0
            }
        
        user = self.users[user_id]
        current_time = time.time()
        
        # Автопополнение червяков
        time_passed = current_time - user.get('last_worm_refill', current_time)
        worms_to_add = int(time_passed // WORM_REFILL_TIME)
        
        if worms_to_add > 0:
            user['worms'] = min(user['worms'] + worms_to_add, MAX_WORMS)
            user['last_worm_refill'] = current_time
        
        # Сброс ежедневных заданий
        last_reset = datetime.fromisoformat(user.get('last_daily_reset', datetime.now().isoformat()))
        if datetime.now().date() > last_reset.date():
            user['daily_quests'] = {}
            user['quests_completed_today'] = 0
            user['last_daily_reset'] = datetime.now().isoformat()
        
        # Очистка старых предупреждений
        user['warnings'] = [w for w in user['warnings'] if current_time - w < WARNING_EXPIRE_TIME]
        
        return user
    
    def use_worm(self, user_id):
        user = self.get_user(user_id)
        if user['worms'] > 0:
            user['worms'] -= 1
            self.save_data()
            return True, user['worms']
        return False, user['worms']
    
    def use_bait(self, user_id, bait_name):
        user = self.get_user(user_id)
        for bait in user['inventory']['baits']:
            if bait['name'] == bait_name and bait['count'] > 0:
                bait['count'] -= 1
                if bait['count'] == 0:
                    user['inventory']['baits'] = [b for b in user['inventory']['baits'] if b['name'] != bait_name]
                self.save_data()
                return True
        return False
    
    def add_fish(self, user_id, fish):
        user = self.get_user(user_id)
        
        catch = {
            'fish': fish['name'],
            'rarity': fish['rarity'],
            'weight': fish['weight'],
            'emoji': fish['emoji'],
            'price': fish.get('price', 0),
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Добавляем в инвентарь рыбы
        fish_name = fish['name']
        if fish_name in user['inventory']['fish']:
            user['inventory']['fish'][fish_name] += 1
        else:
            user['inventory']['fish'][fish_name] = 1
        
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
        
        # Опыт за рыбу
        exp_gained = 0
        if fish['rarity'] == "обычная":
            exp_gained = 10
        elif fish['rarity'] == "редкая":
            exp_gained = 30
        elif fish['rarity'] == "эпическая":
            exp_gained = 100
        elif fish['rarity'] == "легендарная":
            exp_gained = 500
        elif fish['rarity'] == "мусор":
            exp_gained = 1
        
        user['experience'] += exp_gained
        while user['experience'] >= user['fishing_level'] * 100:
            user['experience'] -= user['fishing_level'] * 100
            user['fishing_level'] += 1
        
        self.save_data()
        return catch
    
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
    
    def add_coins(self, user_id, amount):
        user = self.get_user(user_id)
        user['coins'] = max(0, user['coins'] + amount)
        self.save_data()
        return user['coins']
    
    def remove_coins(self, user_id, amount):
        user = self.get_user(user_id)
        if user['coins'] >= amount:
            user['coins'] -= amount
            self.save_data()
            return True, user['coins']
        return False, user['coins']
    
    def add_bait(self, user_id, bait_name, count=1):
        user = self.get_user(user_id)
        for bait in user['inventory']['baits']:
            if bait['name'] == bait_name:
                bait['count'] += count
                self.save_data()
                return True
        
        user['inventory']['baits'].append({"name": bait_name, "count": count})
        self.save_data()
        return True
    
    def add_rod(self, user_id, rod_name):
        user = self.get_user(user_id)
        for rod in user['inventory']['rods']:
            if rod['name'] == rod_name:
                rod['count'] = rod.get('count', 1) + 1
                self.save_data()
                return True
        
        user['inventory']['rods'].append({"name": rod_name, "equipped": False})
        self.save_data()
        return True
    
    def set_current_rod(self, user_id, rod_name):
        user = self.get_user(user_id)
        user['current_rod'] = rod_name
        for rod in user['inventory']['rods']:
            rod['equipped'] = (rod['name'] == rod_name)
        self.save_data()
        return True
    
    def set_current_bait(self, user_id, bait_name):
        user = self.get_user(user_id)
        user['current_bait'] = bait_name
        self.save_data()
        return True
    
    def sell_fish(self, user_id, fish_name, count=1, multiplier=1.0):
        user = self.get_user(user_id)
        
        if fish_name not in user['inventory']['fish'] or user['inventory']['fish'][fish_name] < count:
            return False, 0
        
        # Находим цену рыбы
        fish_price = 0
        for fish in FISHES:
            if fish['name'] == fish_name:
                fish_price = fish.get('price', 0)
                break
        
        if fish_price == 0:
            return False, 0
        
        total_price = int(fish_price * count * multiplier)
        user['inventory']['fish'][fish_name] -= count
        if user['inventory']['fish'][fish_name] == 0:
            del user['inventory']['fish'][fish_name]
        
        user['coins'] += total_price
        self.save_data()
        return True, total_price
    
    def get_daily_quests(self, user_id):
        user = self.get_user(user_id)
        if not user.get('daily_quests'):
            # Генерируем 3 случайных задания
            available_quests = random.sample(DAILY_QUESTS, min(3, len(DAILY_QUESTS)))
            user['daily_quests'] = {q['id']: {'progress': 0, 'completed': False} for q in available_quests}
            self.save_data()
        return user['daily_quests']
    
    def update_quest_progress(self, user_id, quest_type, amount=1):
        user = self.get_user(user_id)
        updated = False
        
        for quest_id, quest_data in user.get('daily_quests', {}).items():
            if quest_data['completed']:
                continue
                
            quest = next((q for q in DAILY_QUESTS if q['id'] == quest_id), None)
            if quest and quest['type'] == quest_type:
                quest_data['progress'] = min(quest_data['progress'] + amount, quest['target'])
                if quest_data['progress'] >= quest['target'] and not quest_data['completed']:
                    quest_data['completed'] = True
                    user['coins'] += quest['reward']
                    user['quests_completed_today'] += 1
                    updated = True
                    self.log_action(user_id, "quest_complete", f"Задание {quest['name']}, награда {quest['reward']}")
        
        if updated:
            self.save_data()
        return updated

db = UserDatabase()

# ========== АДМИН СИСТЕМА ==========
def is_admin(user_id, min_level=1):
    """Проверка, является ли пользователь админом определенного уровня"""
    user_id = str(user_id)
    return ADMINS.get(user_id, 0) >= min_level

def get_admin_level(user_id):
    """Получить уровень админа"""
    user_id = str(user_id)
    return ADMINS.get(user_id, 0)

def set_admin_level(user_id, level):
    """Установить уровень админа"""
    user_id = str(user_id)
    if level <= 0:
        if user_id in ADMINS:
            del ADMINS[user_id]
    else:
        ADMINS[user_id] = level
    db.save_data()
    return True

def get_user_from_input(input_str):
    """Получить user_id из входной строки (может быть ID или @username)"""
    # Если это числовой ID
    if input_str.isdigit():
        return input_str
    
    # Если это @username, ищем в базе
    if input_str.startswith('@'):
        username = input_str[1:].lower()
        for user_id, user_data in db.users.items():
            if user_data.get('username', '').lower() == username:
                return user_id
    
    return None

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def calculate_catch_with_bait(current_bait=None):
    total_prob = sum(RARITY_PROBABILITIES.values())
    rand_num = random.randint(1, total_prob)
    current_prob = 0
    
    # Находим подходящие приманки для рыб
    bait_name = current_bait if current_bait else "🌱 Обычный червь"
    
    for rarity, prob in RARITY_PROBABILITIES.items():
        current_prob += prob
        if rand_num <= current_prob:
            selected_rarity = rarity
            break
    
    # Фильтруем рыбу по доступным приманкам
    available_fish = []
    for fish in FISHES:
        if fish['rarity'] == selected_rarity:
            # Если есть приманка и рыба может на нее клюнуть
            if current_bait and fish.get('baits'):
                # Упрощенная проверка: если в названии приманки есть ключевые слова
                bait_lower = bait_name.lower()
                fish_baits = [b.lower() for b in fish.get('baits', [])]
                
                # Проверяем совпадение по ключевым словам
                keywords = ['червь', 'мотыль', 'опарыш', 'рыба', 'кукуруза', 'горох', 'хлеб']
                has_match = False
                for keyword in keywords:
                    if keyword in bait_lower and any(keyword in b for b in fish_baits):
                        has_match = True
                        break
                
                if has_match or not fish.get('baits'):
                    available_fish.append(fish)
            else:
                available_fish.append(fish)
    
    if not available_fish:
        available_fish = [f for f in FISHES if f['rarity'] == "обычная"]
    
    return random.choice(available_fish)

def create_main_keyboard(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('🎣 Начать рыбалку')
    btn2 = types.KeyboardButton('📊 Статистика')
    btn3 = types.KeyboardButton('🎒 Инвентарь')
    btn4 = types.KeyboardButton('🛒 Магазин')
    btn5 = types.KeyboardButton('💰 Продать рыбу')
    btn6 = types.KeyboardButton('📜 Задания')
    btn7 = types.KeyboardButton('❓ Помощь')
    
    if user_id and is_admin(user_id):
        btn8 = types.KeyboardButton('👑 Админ панель')
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
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if admin_level >= 1:
        btn1 = types.KeyboardButton('🚫 Бан/Разбан')
        btn2 = types.KeyboardButton('📋 Список админов')
        markup.add(btn1, btn2)
    
    if admin_level >= 2:
        btn3 = types.KeyboardButton('📜 Логи банов')
        markup.add(btn3)
    
    if admin_level >= 3:
        btn4 = types.KeyboardButton('🎣 Выдать предметы')
        btn5 = types.KeyboardButton('💰 Выдать монеты')
        markup.add(btn4, btn5)
    
    if admin_level >= 4:
        btn6 = types.KeyboardButton('👤 Статистика игрока')
        markup.add(btn6)
    
    if admin_level >= 5:
        btn7 = types.KeyboardButton('⚙️ Полное управление')
        btn8 = types.KeyboardButton('🗑️ Очистить логи')
        markup.add(btn7, btn8)
    
    btn_back = types.KeyboardButton('📋 Меню')
    markup.add(btn_back)
    
    return markup

def ban_user_in_group(chat_id, user_id, user_name, reason="Нарушение правил", days=2):
    try:
        until_date = int(time.time()) + (days * 86400)
        bot.ban_chat_member(chat_id, user_id, until_date=until_date)
        ban_message = f"🚫 {user_name} забанен на {days} дней!\n⚠️ Причина: {reason}"
        bot.send_message(chat_id, ban_message)
        
        # Логируем бан
        db.log_action(user_id, "banned", f"В чате {chat_id}, причина: {reason}, дней: {days}")
        return True
    except Exception as e:
        print(f"Ошибка бана: {e}")
        try:
            ban_message = f"🚫 {user_name} получил бан на {days} дней! Причина: {reason}"
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
                        ban_user_in_group(chat_id, user.id, user.first_name, "2 ссылки за 24 часа")
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
    user_data = db.get_user(user.id)
    
    # Обновляем имя пользователя если изменилось
    if user.username:
        user_data['username'] = user.username
    user_data['first_name'] = user.first_name
    db.save_data()
    
    if db.is_banned(str(user.id)):
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
    
    welcome_text = (
        f"🎣 Привет, {user.first_name}!\n"
        f"Добро пожаловать в мир рыбалки!\n\n"
        f"🐛 Червяков: {user_data['worms']}/10\n"
        f"💰 {COINS_NAME}: {user_data['coins']}\n"
        f"🐟 Всего поймано: {user_data['total_fish']}\n"
        f"🎣 Уровень: {user_data['fishing_level']}\n\n"
        f"♻️ Червяки пополняются каждые 15 минут!\n\n"
        f"Используй кнопки ниже для игры!\n\n"
        f"Если хотите поддержать: ||2200702034105283||"
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
        "/shop - Магазин снастей\n"
        "/sell - Продать рыбу\n"
        "/quests - Ежедневные задания\n"
        "/help - Эта справка\n\n"
        "🎮 *Как играть:*\n"
        "1️⃣ У вас есть червяки 🐛 (макс. 10)\n"
        "2️⃣ Каждая рыбалка тратит 1 червяка\n"
        "3️⃣ Червяки восстанавливаются (1 каждые 15 минут)\n"
        "4️⃣ Рыбалка длится 30 секунд\n"
        "5️⃣ Используйте разные приманки для разной рыбы\n\n"
        "🐟 *Редкости рыбы:*\n"
        "• 🐟 Обычная (50%)\n"
        "• 🐠 Редкая (30%)\n"
        "• 🌟 Эпическая (15%)\n"
        "• 👑 Легендарная (4%)\n"
        "• 🗑️ Мусор (1%)\n\n"
        "🛒 *Магазин:*\n"
        "• Покупайте червей и снасти\n"
        "• Разные приманки для разной рыбы\n"
        "• Улучшенные удочки увеличивают шансы\n\n"
        "💰 *Продажа рыбы:*\n"
        "• Продавайте рыбу NPC-торговцам\n"
        "• Разные NPC дают разную цену\n\n"
        "⚖️ *Правила чата (в группах):*\n"
        "• Запрещены любые ссылки (кроме @username)\n"
        "• 1 ссылка = предупреждение\n"
        "• 2 ссылки за 24 часа = бан на 2 дня в группе\n"
        "• @username разрешены\n\n"
        "Удачи на рыбалке! 🎣"
    )
    
    bot.send_message(message.chat.id, help_text, reply_markup=create_main_keyboard(message.from_user.id))

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
        f"💰 {COINS_NAME}: {user_data['coins']}\n"
        f"🎣 Уровень: {user_data['fishing_level']}\n"
        f"📈 Опыт: {user_data['experience']}/{user_data['fishing_level'] * 100}\n"
        f"⚠️ Предупреждений: {warning_count}/2\n\n"
        f"🎣 *Снаряжение:*\n"
        f"• Удочка: {user_data['current_rod']}\n"
        f"• Приманка: {user_data['current_bait']}\n\n"
        f"🐟 *Поймано:*\n"
        f"• 🐟 Обычных: {user_data['stats']['common']}\n"
        f"• 🐠 Редких: {user_data['stats']['rare']}\n"
        f"• 🌟 Эпических: {user_data['stats']['epic']}\n"
        f"• 👑 Легендарных: {user_data['stats']['legendary']}\n"
        f"• 🗑️ Мусора: {user_data['stats']['trash']}\n\n"
        f"🎯 Удача: {luck_rate:.1f}% | Мусор: {trash_rate:.1f}%\n"
        f"🎣 Всего попыток: {user_data['total_fish']}"
    )
    bot.send_message(message.chat.id, stats_text, reply_markup=create_main_keyboard(user.id))

@bot.message_handler(commands=['inventory'])
def inventory_command(message):
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    user_data = db.get_user(user.id)
    
    inventory_text = f"🎒 *Инвентарь {user.first_name}*\n\n"
    
    # Рыба
    if user_data['inventory']['fish']:
        inventory_text += "🐟 *Рыба:*\n"
        for fish_name, count in user_data['inventory']['fish'].items():
            inventory_text += f"• {fish_name}: {count} шт\n"
        inventory_text += "\n"
    else:
        inventory_text += "🐟 Рыбы нет\n\n"
    
    # Приманки
    if user_data['inventory']['baits']:
        inventory_text += "🎣 *Приманки:*\n"
        for bait in user_data['inventory']['baits']:
            inventory_text += f"• {bait['name']}: {bait['count']} шт\n"
        inventory_text += "\n"
    
    # Удочки
    if user_data['inventory']['rods']:
        inventory_text += "🎣 *Удочки:*\n"
        for rod in user_data['inventory']['rods']:
            equipped = "✅" if rod.get('equipped', False) else ""
            inventory_text += f"• {rod['name']} {equipped}\n"
    
    bot.send_message(message.chat.id, inventory_text, reply_markup=create_main_keyboard(user.id))

@bot.message_handler(commands=['shop'])
def shop_command(message):
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🪱 Приманки', callback_data='shop_baits')
    btn2 = types.InlineKeyboardButton('🎣 Удочки', callback_data='shop_rods')
    btn3 = types.InlineKeyboardButton('🐛 Купить червяков', callback_data='shop_worms')
    btn4 = types.InlineKeyboardButton('📋 Меню', callback_data='menu')
    markup.add(btn1, btn2, btn3, btn4)
    
    user_data = db.get_user(user.id)
    shop_text = (
        f"🛒 *Магазин рыболовных снастей*\n\n"
        f"💰 Ваш баланс: {user_data['coins']} {COINS_NAME}\n\n"
        f"Выберите категорию:"
    )
    
    bot.send_message(message.chat.id, shop_text, reply_markup=markup)

@bot.message_handler(commands=['sell'])
def sell_command(message):
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    user_data = db.get_user(user.id)
    
    if not user_data['inventory']['fish']:
        bot.send_message(message.chat.id, "🎣 У вас нет рыбы для продажи!", reply_markup=create_main_keyboard(user.id))
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Создаем кнопки для NPC-продавцов
    for i, npc in enumerate(NPC_SELLERS):
        btn = types.InlineKeyboardButton(f"{npc['emoji']} {npc['name']}", callback_data=f'sell_npc_{i}')
        markup.add(btn)
    
    btn_back = types.InlineKeyboardButton('📋 Меню', callback_data='menu')
    markup.add(btn_back)
    
    sell_text = (
        f"💰 *Продажа рыбы*\n\n"
        f"🐟 Ваша рыба:\n"
    )
    
    for fish_name, count in user_data['inventory']['fish'].items():
        # Находим базовую цену
        base_price = 0
        for fish in FISHES:
            if fish['name'] == fish_name:
                base_price = fish.get('price', 0)
                break
        
        if base_price > 0:
            sell_text += f"• {fish_name}: {count} шт (по {base_price} {COINS_NAME})\n"
    
    sell_text += "\nВыберите покупателя:"
    
    bot.send_message(message.chat.id, sell_text, reply_markup=markup)

@bot.message_handler(commands=['quests'])
def quests_command(message):
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    user_data = db.get_user(user.id)
    daily_quests = db.get_daily_quests(user.id)
    
    quests_text = f"📜 *Ежедневные задания*\n\n"
    quests_text += f"✅ Выполнено сегодня: {user_data['quests_completed_today']}/3\n\n"
    
    for quest_id, quest_data in daily_quests.items():
        quest = next((q for q in DAILY_QUESTS if q['id'] == quest_id), None)
        if quest:
            status = "✅" if quest_data['completed'] else f"{quest_data['progress']}/{quest['target']}"
            quests_text += f"{quest['emoji'] if 'emoji' in quest else '🎯'} *{quest['name']}*\n"
            quests_text += f"📝 {quest['description']}\n"
            quests_text += f"📊 Прогресс: {status}\n"
            quests_text += f"💰 Награда: {quest['reward']} {COINS_NAME}\n\n"
    
    if not daily_quests:
        quests_text += "🎯 Задания обновятся завтра!"
    
    bot.send_message(message.chat.id, quests_text, reply_markup=create_main_keyboard(user.id))

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
                           f"😔 Червяки закончились!\n"
                           f"Следующий червяк через: {minutes} мин {seconds} сек",
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
    
    # Проверяем, есть ли приманка
    bait_used = False
    current_bait = user_data['current_bait']
    
    if current_bait != "🌱 Обычный червь":
        for bait in user_data['inventory']['baits']:
            if bait['name'] == current_bait and bait['count'] > 0:
                bait_used = db.use_bait(user.id, current_bait)
                break
    
    msg = bot.send_message(message.chat.id,
                          f"🎣 *Началась рыбалка!*\n\n"
                          f"🐛 Потрачен 1 червяк\n"
                          f"🎣 Приманка: {current_bait}\n"
                          f"🕐 Осталось червяков: {worms_left}\n"
                          f"⏳ Рыбалка продлится {FISHING_TIME} секунд\n\n"
                          f"Ждите... рыба клюёт!",
                          reply_markup=create_fishing_keyboard())
    
    def fishing_timer():
        time.sleep(FISHING_TIME)
        
        if user_id in db.active_fishing:
            del db.active_fishing[user_id]
        
        caught_fish = calculate_catch_with_bait(current_bait)
        catch_info = db.add_fish(user.id, caught_fish)
        user_data = db.get_user(user.id)
        
        # Обновляем прогресс заданий
        db.update_quest_progress(user.id, "catch")
        if caught_fish['rarity'] == "редкая":
            db.update_quest_progress(user.id, "catch_rare")
        elif caught_fish['rarity'] == "эпическая":
            db.update_quest_progress(user.id, "catch_epic")
        elif caught_fish['rarity'] == "легендарная":
            db.update_quest_progress(user.id, "catch_legendary")
        
        rarity_emojis = {
            'обычная': '🐟',
            'редкая': '🐠',
            'эпическая': '🌟',
            'легендарная': '👑',
            'мусор': '🗑️'
        }
        
        bait_text = f"\n🎣 Использована приманка: {current_bait}" if bait_used else ""
        
        result_text = (
            f"🎉 *Рыбалка завершена!*\n\n"
            f"{rarity_emojis.get(caught_fish['rarity'], '🎣')} *Поймано:* {caught_fish['name']}\n"
            f"📊 *Редкость:* {caught_fish['rarity']}\n"
            f"⚖️ *Вес:* {caught_fish['weight']}\n"
            f"{bait_text}\n\n"
            f"🐛 Червяков осталось: {user_data['worms']}\n"
            f"💰 {COINS_NAME}: {user_data['coins']}\n"
            f"🐟 Всего поймано: {user_data['total_fish']}\n\n"
        )
        
        if caught_fish['rarity'] == 'легендарная':
            result_text += "🎊 *ВАУ! Легендарная рыба!* 🎊\n\n"
        elif caught_fish['rarity'] == 'мусор':
            result_text += "😔 Не повезло... Попробуйте еще раз!\n\n"
        
        try:
            bot.send_message(message.chat.id, result_text, reply_markup=create_main_keyboard(user.id))
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    db.active_fishing[user_id] = threading.Thread(target=fishing_timer)
    db.active_fishing[user_id].daemon = True
    db.active_fishing[user_id].start()

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['+админ', '+admin'])
def add_admin_command(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "❌ Формат: /+админ @username/id уровень")
        return
    
    target = parts[1]
    try:
        level = int(parts[2])
        if level < 1 or level > 5:
            bot.send_message(message.chat.id, "❌ Уровень должен быть от 1 до 5")
            return
    except:
        bot.send_message(message.chat.id, "❌ Уровень должен быть числом")
        return
    
    target_id = get_user_from_input(target)
    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    set_admin_level(target_id, level)
    db.log_admin_action(user.id, "add_admin", target_id, f"Уровень {level}")
    
    # Получаем имя пользователя
    target_user = db.get_user(target_id)
    target_name = target_user.get('first_name', 'Неизвестно')
    
    bot.send_message(message.chat.id, f"✅ Админ добавлен: {target_name} (ID: {target_id}), уровень: {level}")

@bot.message_handler(commands=['-админ', '-admin'])
def remove_admin_command(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Формат: /-админ @username/id")
        return
    
    target = parts[1]
    target_id = get_user_from_input(target)
    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    if target_id == str(user.id):
        bot.send_message(message.chat.id, "❌ Нельзя снять себя!")
        return
    
    old_level = get_admin_level(target_id)
    set_admin_level(target_id, 0)
    db.log_admin_action(user.id, "remove_admin", target_id)
    
    target_user = db.get_user(target_id)
    target_name = target_user.get('first_name', 'Неизвестно')
    
    bot.send_message(message.chat.id, f"✅ Админ снят: {target_name} (ID: {target_id}), был уровень: {old_level}")

@bot.message_handler(commands=['бан', 'ban'])
def ban_admin_command(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "❌ Формат: /бан @username/id дни причина")
        bot.send_message(message.chat.id, "Пример: /бан @monstrov 7 неадекват")
        return
    
    target = parts[1]
    try:
        days = int(parts[2])
        if days < 1 or days > 365:
            bot.send_message(message.chat.id, "❌ Дни должны быть от 1 до 365")
            return
    except:
        bot.send_message(message.chat.id, "❌ Дни должны быть числом")
        return
    
    reason = ' '.join(parts[3:]) if len(parts) > 3 else "Нарушение правил"
    
    target_id = get_user_from_input(target)
    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    # Проверяем уровень админа
    target_admin_level = get_admin_level(target_id)
    if target_admin_level >= get_admin_level(user.id):
        bot.send_message(message.chat.id, "❌ Нельзя забанить админа равного или выше уровнем!")
        return
    
    target_user = db.get_user(target_id)
    target_name = target_user.get('first_name', 'Неизвестно')
    
    # Баним в базе данных
    target_user['banned_until'] = time.time() + (days * 86400)
    db.save_data()
    
    # Пытаемся забанить в чате, если это группа
    if message.chat.type in ['group', 'supergroup']:
        try:
            until_date = int(time.time()) + (days * 86400)
            bot.ban_chat_member(message.chat.id, int(target_id), until_date=until_date)
        except:
            pass
    
    db.log_admin_action(user.id, "ban", target_id, f"{days} дней, причина: {reason}")
    
    response = (
        f"🚫 *Пользователь забанен*\n\n"
        f"👤 Имя: {target_name}\n"
        f"🆔 ID: {target_id}\n"
        f"⏳ Срок: {days} дней\n"
        f"📝 Причина: {reason}\n\n"
        f"✅ Бан выдан администратором: {user.first_name}"
    )
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['разбан', 'unban'])
def unban_admin_command(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Формат: /разбан @username/id")
        return
    
    target = parts[1]
    target_id = get_user_from_input(target)
    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    target_user = db.get_user(target_id)
    target_name = target_user.get('first_name', 'Неизвестно')
    
    # Разбаниваем в базе данных
    target_user['banned_until'] = None
    db.save_data()
    
    # Пытаемся разбанить в чате, если это группа
    if message.chat.type in ['group', 'supergroup']:
        try:
            bot.unban_chat_member(message.chat.id, int(target_id))
        except:
            pass
    
    db.log_admin_action(user.id, "unban", target_id)
    
    response = (
        f"✅ *Пользователь разбанен*\n\n"
        f"👤 Имя: {target_name}\n"
        f"🆔 ID: {target_id}\n\n"
        f"✅ Разбан выдан администратором: {user.first_name}"
    )
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['статадмин', 'statsadmin'])
def admin_stats_command(message):
    user = message.from_user
    if not is_admin(user.id, 4):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Формат: /статадмин @username/id")
        return
    
    target = parts[1]
    target_id = get_user_from_input(target)
    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    target_user = db.get_user(target_id)
    
    stats_text = (
        f"👤 *Полная статистика игрока*\n\n"
        f"📝 Имя: {target_user.get('first_name', 'Неизвестно')}\n"
        f"🆔 ID: {target_id}\n"
        f"📊 Уровень админа: {get_admin_level(target_id)}\n\n"
        f"💰 {COINS_NAME}: {target_user['coins']}\n"
        f"🐛 Червяков: {target_user['worms']}/10\n"
        f"🎣 Уровень рыбалки: {target_user['fishing_level']}\n"
        f"🐟 Всего поймано: {target_user['total_fish']}\n\n"
        f"🎣 *Снаряжение:*\n"
        f"• Удочка: {target_user['current_rod']}\n"
        f"• Приманка: {target_user['current_bait']}\n\n"
        f"🎒 *Инвентарь:*\n"
    )
    
    # Рыба
    if target_user['inventory']['fish']:
        stats_text += "🐟 Рыба:\n"
        for fish_name, count in target_user['inventory']['fish'].items():
            stats_text += f"  • {fish_name}: {count} шт\n"
        stats_text += "\n"
    
    # Приманки
    if target_user['inventory']['baits']:
        stats_text += "🎣 Приманки:\n"
        for bait in target_user['inventory']['baits']:
            stats_text += f"  • {bait['name']}: {bait['count']} шт\n"
        stats_text += "\n"
    
    # Удочки
    if target_user['inventory']['rods']:
        stats_text += "🎣 Удочки:\n"
        for rod in target_user['inventory']['rods']:
            equipped = "(активна)" if rod.get('equipped', False) else ""
            stats_text += f"  • {rod['name']} {equipped}\n"
    
    bot.send_message(message.chat.id, stats_text)

@bot.message_handler(commands=['выдать', 'give'])
def give_admin_command(message):
    user = message.from_user
    if not is_admin(user.id, 3):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 4:
        bot.send_message(message.chat.id, "❌ Формат: /выдать @username/id тип количество")
        bot.send_message(message.chat.id, "Типы: coins, bait, rod, fish")
        return
    
    target = parts[1]
    item_type = parts[2].lower()
    
    try:
        amount = int(parts[3])
        if amount <= 0:
            bot.send_message(message.chat.id, "❌ Количество должно быть положительным")
            return
    except:
        bot.send_message(message.chat.id, "❌ Количество должно быть числом")
        return
    
    target_id = get_user_from_input(target)
    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    target_user = db.get_user(target_id)
    target_name = target_user.get('first_name', 'Неизвестно')
    
    if item_type == 'coins':
        db.add_coins(target_id, amount)
        db.log_admin_action(user.id, "give_coins", target_id, f"{amount} {COINS_NAME}")
        response = f"✅ Выдано {amount} {COINS_NAME} игроку {target_name}"
    
    elif item_type == 'bait':
        if len(parts) < 5:
            bot.send_message(message.chat.id, "❌ Укажите название приманки")
            return
        
        bait_name = ' '.join(parts[4:])
        # Ищем приманку
        bait_found = False
        for bait in BAITS:
            if bait['name'] == bait_name:
                db.add_bait(target_id, bait_name, amount)
                db.log_admin_action(user.id, "give_bait", target_id, f"{bait_name} x{amount}")
                response = f"✅ Выдано {amount} шт. приманки '{bait_name}' игроку {target_name}"
                bait_found = True
                break
        
        if not bait_found:
            response = f"❌ Приманка '{bait_name}' не найдена"
    
    elif item_type == 'rod':
        if len(parts) < 5:
            bot.send_message(message.chat.id, "❌ Укажите название удочки")
            return
        
        rod_name = ' '.join(parts[4:])
        # Ищем удочку
        rod_found = False
        for rod in RODS:
            if rod['name'] == rod_name:
                for i in range(amount):
                    db.add_rod(target_id, rod_name)
                db.log_admin_action(user.id, "give_rod", target_id, f"{rod_name} x{amount}")
                response = f"✅ Выдано {amount} шт. удочки '{rod_name}' игроку {target_name}"
                rod_found = True
                break
        
        if not rod_found:
            response = f"❌ Удочка '{rod_name}' не найдена"
    
    elif item_type == 'fish':
        if len(parts) < 5:
            bot.send_message(message.chat.id, "❌ Укажите название рыбы")
            return
        
        fish_name = ' '.join(parts[4:])
        # Ищем рыбу
        fish_found = False
        for fish in FISHES:
            if fish['name'] == fish_name:
                # Добавляем рыбу в инвентарь
                if fish_name in target_user['inventory']['fish']:
                    target_user['inventory']['fish'][fish_name] += amount
                else:
                    target_user['inventory']['fish'][fish_name] = amount
                
                db.save_data()
                db.log_admin_action(user.id, "give_fish", target_id, f"{fish_name} x{amount}")
                response = f"✅ Выдано {amount} шт. рыбы '{fish_name}' игроку {target_name}"
                fish_found = True
                break
        
        if not fish_found:
            response = f"❌ Рыба '{fish_name}' не найдена"
    
    else:
        response = "❌ Неизвестный тип предмета"
    
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['логи', 'logs'])
def logs_admin_command(message):
    user = message.from_user
    admin_level = get_admin_level(user.id)
    
    if admin_level < 2:
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    log_type = parts[1].lower() if len(parts) > 1 else "bans"
    
    if log_type == "bans" and admin_level >= 2:
        # Логи банов
        ban_logs = [log for log in db.admin_logs if log['action'] in ['ban', 'unban']]
        
        if not ban_logs:
            bot.send_message(message.chat.id, "📜 Логов банов нет")
            return
        
        logs_text = "📜 *Логи банов/разбанов*\n\n"
        for log in ban_logs[-10:]:  # Последние 10 записей
            action_ru = "Бан" if log['action'] == 'ban' else "Разбан"
            timestamp = datetime.fromisoformat(log['timestamp']).strftime("%d.%m %H:%M")
            logs_text += f"⏰ {timestamp} | {action_ru} | ID: {log['target_id']}\n"
            if 'details' in log:
                logs_text += f"   📝 {log['details']}\n"
            logs_text += f"   👮 Админ: {log['admin_id']}\n\n"
        
        bot.send_message(message.chat.id, logs_text)
    
    elif log_type == "actions" and admin_level >= 5:
        # Логи действий (только для 5 уровня)
        if not db.action_logs:
            bot.send_message(message.chat.id, "📜 Логов действий нет")
            return
        
        logs_text = "📜 *Логи действий пользователей*\n\n"
        for log in db.action_logs[-15:]:  # Последние 15 записей
            timestamp = datetime.fromisoformat(log['timestamp']).strftime("%d.%m %H:%M")
            logs_text += f"⏰ {timestamp} | ID: {log['user_id']}\n"
            logs_text += f"   📝 {log['action_type']}\n"
            if 'details' in log:
                logs_text += f"   ℹ️ {log['details']}\n"
            logs_text += "\n"
        
        bot.send_message(message.chat.id, logs_text)
    
    elif log_type == "admin" and admin_level >= 2:
        # Логи действий админов
        if not db.admin_logs:
            bot.send_message(message.chat.id, "📜 Логов админов нет")
            return
        
        logs_text = "📜 *Логи действий админов*\n\n"
        for log in db.admin_logs[-10:]:  # Последние 10 записей
            timestamp = datetime.fromisoformat(log['timestamp']).strftime("%d.%m %H:%M")
            logs_text += f"⏰ {timestamp} | 👮 ID: {log['admin_id']}\n"
            logs_text += f"   📝 Действие: {log['action']}\n"
            if log['target_id']:
                logs_text += f"   🎯 Цель: {log['target_id']}\n"
            if 'details' in log:
                logs_text += f"   ℹ️ {log['details']}\n"
            logs_text += "\n"
        
        bot.send_message(message.chat.id, logs_text)
    
    else:
        bot.send_message(message.chat.id, "❌ Неизвестный тип логов или недостаточно прав")

@bot.message_handler(commands=['админы', 'admins'])
def list_admins_command(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    admins_text = "👑 *Список администраторов*\n\n"
    
    for admin_id, level in ADMINS.items():
        admin_user = db.get_user(admin_id)
        admin_name = admin_user.get('first_name', 'Неизвестно')
        admins_text += f"🎖️ Уровень {level}: {admin_name}\n"
        admins_text += f"   🆔 ID: {admin_id}\n"
        if admin_user.get('username'):
            admins_text += f"   👤 @{admin_user['username']}\n"
        admins_text += "\n"
    
    bot.send_message(message.chat.id, admins_text)

@bot.message_handler(commands=['очиститьлоги', 'clearlogs'])
def clear_logs_command(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Формат: /очиститьлоги тип")
        bot.send_message(message.chat.id, "Типы: all, admin, action")
        return
    
    log_type = parts[1].lower()
    
    if log_type == 'all':
        db.admin_logs = []
        db.action_logs = []
        response = "✅ Все логи очищены"
    elif log_type == 'admin':
        db.admin_logs = []
        response = "✅ Логи админов очищены"
    elif log_type == 'action':
        db.action_logs = []
        response = "✅ Логи действий очищены"
    else:
        response = "❌ Неизвестный тип логов"
    
    db.save_logs()
    db.log_admin_action(user.id, "clear_logs", details=log_type)
    bot.send_message(message.chat.id, response)

@bot.message_handler(commands=['сбросить', 'reset'])
def reset_user_command(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Формат: /сбросить @username/id что")
        bot.send_message(message.chat.id, "Что: stats, inventory, all")
        return
    
    target = parts[1]
    reset_type = parts[2].lower() if len(parts) > 2 else "stats"
    
    target_id = get_user_from_input(target)
    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    target_user = db.get_user(target_id)
    target_name = target_user.get('first_name', 'Неизвестно')
    
    if reset_type == 'stats':
        target_user['stats'] = {'common': 0, 'rare': 0, 'epic': 0, 'legendary': 0, 'trash': 0}
        target_user['total_fish'] = 0
        target_user['fishing_level'] = 1
        target_user['experience'] = 0
        response = f"✅ Статистика игрока {target_name} сброшена"
    
    elif reset_type == 'inventory':
        target_user['inventory'] = {
            'rods': [{"name": "🎣 Простая удочка", "equipped": True}],
            'baits': [{"name": "🌱 Обычный червь", "count": 10}],
            'fish': {}
        }
        target_user['current_rod'] = "🎣 Простая удочка"
        target_user['current_bait'] = "🌱 Обычный червь"
        response = f"✅ Инвентарь игрока {target_name} сброшен"
    
    elif reset_type == 'all':
        # Полный сброс (кроме бана)
        banned_until = target_user.get('banned_until')
        warnings = target_user.get('warnings', [])
        
        new_user_data = {
            'worms': INITIAL_WORMS,
            'fish_caught': [],
            'total_fish': 0,
            'last_fishing_time': None,
            'last_worm_refill': time.time(),
            'stats': {'common': 0, 'rare': 0, 'epic': 0, 'legendary': 0, 'trash': 0},
            'username': target_user.get('username'),
            'first_name': target_user.get('first_name'),
            'warnings': warnings,
            'banned_until': banned_until,
            'coins': INITIAL_COINS,
            'inventory': {
                'rods': [{"name": "🎣 Простая удочка", "equipped": True}],
                'baits': [{"name": "🌱 Обычный червь", "count": 10}],
                'fish': {}
            },
            'daily_quests': {},
            'quests_completed_today': 0,
            'last_daily_reset': datetime.now().isoformat(),
            'current_rod': "🎣 Простая удочка",
            'current_bait': "🌱 Обычный червь",
            'favorite_fishing_spots': [],
            'achievements': [],
            'fishing_level': 1,
            'experience': 0
        }
        
        db.users[target_id] = new_user_data
        response = f"✅ Игрок {target_name} полностью сброшен"
    
    else:
        response = "❌ Неизвестный тип сброса"
    
    db.save_data()
    db.log_admin_action(user.id, "reset", target_id, reset_type)
    bot.send_message(message.chat.id, response)

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

@bot.message_handler(func=lambda msg: msg.text == '🛒 Магазин')
def shop_button_handler(message):
    shop_command(message)

@bot.message_handler(func=lambda msg: msg.text == '💰 Продать рыбу')
def sell_button_handler(message):
    sell_command(message)

@bot.message_handler(func=lambda msg: msg.text == '📜 Задания')
def quests_button_handler(message):
    quests_command(message)

@bot.message_handler(func=lambda msg: msg.text == '❓ Помощь')
def help_button_handler(message):
    help_command(message)

@bot.message_handler(func=lambda msg: msg.text == '👑 Админ панель')
def admin_panel_handler(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        bot.send_message(message.chat.id, "❌ У вас нет доступа к админ панели!", reply_markup=create_main_keyboard(user.id))
        return
    
    admin_level = get_admin_level(user.id)
    admin_text = (
        f"👑 *Админ панель*\n\n"
        f"🎖️ Ваш уровень: {admin_level}/5\n"
        f"👤 Ваш ID: {user.id}\n\n"
        f"📋 *Доступные команды:*\n"
    )
    
    if admin_level >= 1:
        admin_text += "• /бан @user дни причина - Забанить\n• /разбан @user - Разбанить\n"
    if admin_level >= 2:
        admin_text += "• /логи bans - Логи банов\n• /логи admin - Логи админов\n"
    if admin_level >= 3:
        admin_text += "• /выдать @user coins сумма - Выдать монеты\n• /выдать @user bait сумма название - Выдать приманку\n"
    if admin_level >= 4:
        admin_text += "• /статадмин @user - Полная статистика\n"
    if admin_level >= 5:
        admin_text += "• /очиститьлоги тип - Очистить логи\n• /сбросить @user тип - Сбросить данные\n• /+админ @user уровень - Добавить админа\n• /-админ @user - Удалить админа\n"
    
    admin_text += "\nВыберите действие:"
    
    bot.send_message(message.chat.id, admin_text, reply_markup=create_admin_keyboard(admin_level))

@bot.message_handler(func=lambda msg: msg.text == '📋 Меню')
def menu_command(message):
    user = message.from_user
    bot.send_message(message.chat.id, "Возвращаю в главное меню:", reply_markup=create_main_keyboard(user.id))

@bot.message_handler(func=lambda msg: msg.text == '🚫 Бан/Разбан')
def admin_ban_menu_handler(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        return
    
    bot.send_message(message.chat.id, 
                    "🚫 *Управление банами*\n\n"
                    "📋 Команды:\n"
                    "/бан @username дни причина - Забанить\n"
                    "/разбан @username - Разбанить\n\n"
                    "Пример:\n"
                    "/бан @monstrov 7 неадекват\n"
                    "/разбан @monstrov",
                    reply_markup=create_admin_keyboard(get_admin_level(user.id)))

@bot.message_handler(func=lambda msg: msg.text == '📋 Список админов')
def admin_list_handler(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        return
    
    list_admins_command(message)

@bot.message_handler(func=lambda msg: msg.text == '📜 Логи банов')
def admin_logs_handler(message):
    user = message.from_user
    if not is_admin(user.id, 2):
        return
    
    logs_admin_command(message)

@bot.message_handler(func=lambda msg: msg.text == '🎣 Выдать предметы')
def admin_give_handler(message):
    user = message.from_user
    if not is_admin(user.id, 3):
        return
    
    bot.send_message(message.chat.id,
                    "🎣 *Выдача предметов*\n\n"
                    "📋 Команды:\n"
                    "/выдать @user coins сумма - Монеты\n"
                    "/выдать @user bait сумма название - Приманка\n"
                    "/выдать @user rod сумма название - Удочка\n"
                    "/выдать @user fish сумма название - Рыба\n\n"
                    "Пример:\n"
                    "/выдать @monstrov coins 1000\n"
                    "/выдать @monstrov bait 10 🔴 Мотыль",
                    reply_markup=create_admin_keyboard(get_admin_level(user.id)))

@bot.message_handler(func=lambda msg: msg.text == '💰 Выдать монеты')
def admin_coins_handler(message):
    user = message.from_user
    if not is_admin(user.id, 3):
        return
    
    bot.send_message(message.chat.id,
                    "💰 *Выдача монет*\n\n"
                    "📋 Команда:\n"
                    "/выдать @user coins сумма\n\n"
                    "Пример:\n"
                    "/выдать @monstrov coins 5000",
                    reply_markup=create_admin_keyboard(get_admin_level(user.id)))

@bot.message_handler(func=lambda msg: msg.text == '👤 Статистика игрока')
def admin_player_stats_handler(message):
    user = message.from_user
    if not is_admin(user.id, 4):
        return
    
    bot.send_message(message.chat.id,
                    "👤 *Статистика игрока*\n\n"
                    "📋 Команда:\n"
                    "/статадмин @username/id\n\n"
                    "Пример:\n"
                    "/статадмин @monstrov\n"
                    "/статадмин 5330661807",
                    reply_markup=create_admin_keyboard(get_admin_level(user.id)))

@bot.message_handler(func=lambda msg: msg.text == '⚙️ Полное управление')
def admin_full_control_handler(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        return
    
    bot.send_message(message.chat.id,
                    "⚙️ *Полное управление*\n\n"
                    "📋 Команды 5 уровня:\n\n"
                    "👑 Админы:\n"
                    "/+админ @user уровень - Добавить админа\n"
                    "/-админ @user - Удалить админа\n\n"
                    "🗑️ Очистка:\n"
                    "/очиститьлоги all - Все логи\n"
                    "/очиститьлоги admin - Логи админов\n"
                    "/очиститьлоги action - Логи действий\n\n"
                    "🔄 Сброс:\n"
                    "/сбросить @user stats - Статистика\n"
                    "/сбросить @user inventory - Инвентарь\n"
                    "/сбросить @user all - Полный сброс\n\n"
                    "📜 Логи:\n"
                    "/логи actions - Все действия\n"
                    "/логи admin - Действия админов\n"
                    "/логи bans - Баны/разбаны",
                    reply_markup=create_admin_keyboard(get_admin_level(user.id)))

@bot.message_handler(func=lambda msg: msg.text == '🗑️ Очистить логи')
def admin_clear_logs_handler(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        return
    
    bot.send_message(message.chat.id,
                    "🗑️ *Очистка логов*\n\n"
                    "📋 Команды:\n"
                    "/очиститьлоги all - Все логи\n"
                    "/очиститьлоги admin - Логи админов\n"
                    "/очиститьлоги action - Логи действий\n\n"
                    "⚠️ Внимание: действие необратимо!",
                    reply_markup=create_admin_keyboard(get_admin_level(user.id)))

# ========== CALLBACK ОБРАБОТЧИКИ ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user = call.from_user
    
    if call.data == 'menu':
        bot.edit_message_text("Возвращаю в главное меню:", 
                            call.message.chat.id, 
                            call.message.message_id)
        bot.send_message(call.message.chat.id, "Выберите действие:", reply_markup=create_main_keyboard(user.id))
    
    elif call.data == 'shop_baits':
        markup = types.InlineKeyboardMarkup(row_width=2)
        user_data = db.get_user(user.id)
        
        for bait in BAITS:
            btn = types.InlineKeyboardButton(f"{bait['emoji']} {bait['name']} - {bait['price']}р", 
                                           callback_data=f'buy_bait_{bait["name"]}')
            markup.add(btn)
        
        btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='shop_back')
        markup.add(btn_back)
        
        text = f"🪱 *Магазин приманок*\n\n💰 Ваш баланс: {user_data['coins']} {COINS_NAME}\n\nВыберите приманку:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data == 'shop_rods':
        markup = types.InlineKeyboardMarkup(row_width=2)
        user_data = db.get_user(user.id)
        
        for rod in RODS:
            btn = types.InlineKeyboardButton(f"{rod['emoji']} {rod['name']} - {rod['price']}р", 
                                           callback_data=f'buy_rod_{rod["name"]}')
            markup.add(btn)
        
        btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='shop_back')
        markup.add(btn_back)
        
        text = f"🎣 *Магазин удочек*\n\n💰 Ваш баланс: {user_data['coins']} {COINS_NAME}\n\nВыберите удочку:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data == 'shop_worms':
        markup = types.InlineKeyboardMarkup()
        user_data = db.get_user(user.id)
        
        btn1 = types.InlineKeyboardButton(f"🐛 1 червяк - {WORM_PRICE}р", callback_data=f'buy_worms_1')
        btn3 = types.InlineKeyboardButton(f"🐛🐛🐛 3 червяка - {WORM_PRICE*3}р", callback_data=f'buy_worms_3')
        btn5 = types.InlineKeyboardButton(f"🐛x5 5 червяков - {WORM_PRICE*5}р", callback_data=f'buy_worms_5')
        btn10 = types.InlineKeyboardButton(f"📦 10 червяков - {WORM_PRICE*8}р", callback_data=f'buy_worms_10')
        btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='shop_back')
        
        markup.add(btn1, btn3, btn5, btn10, btn_back)
        
        text = f"🐛 *Покупка червяков*\n\n💰 Ваш баланс: {user_data['coins']} {COINS_NAME}\n🐛 Сейчас: {user_data['worms']}/10\n\nВыберите количество:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data == 'shop_back':
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn1 = types.InlineKeyboardButton('🪱 Приманки', callback_data='shop_baits')
        btn2 = types.InlineKeyboardButton('🎣 Удочки', callback_data='shop_rods')
        btn3 = types.InlineKeyboardButton('🐛 Купить червяков', callback_data='shop_worms')
        btn4 = types.InlineKeyboardButton('📋 Меню', callback_data='menu')
        markup.add(btn1, btn2, btn3, btn4)
        
        user_data = db.get_user(user.id)
        text = f"🛒 *Магазин рыболовных снастей*\n\n💰 Ваш баланс: {user_data['coins']} {COINS_NAME}\n\nВыберите категорию:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data.startswith('buy_bait_'):
        bait_name = call.data[9:]
        bait = next((b for b in BAITS if b['name'] == bait_name), None)
        
        if not bait:
            bot.answer_callback_query(call.id, "❌ Приманка не найдена!")
            return
        
        user_data = db.get_user(user.id)
        
        if user_data['coins'] < bait['price']:
            bot.answer_callback_query(call.id, f"❌ Недостаточно {COINS_NAME}! Нужно {bait['price']}, у вас {user_data['coins']}")
            return
        
        success, new_balance = db.remove_coins(user.id, bait['price'])
        if success:
            db.add_bait(user.id, bait_name)
            db.update_quest_progress(user.id, "buy_bait")
            db.log_action(user.id, "buy_bait", bait_name)
            
            # Обновляем сообщение
            markup = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton('🛒 Продолжить покупки', callback_data='shop_baits')
            btn_menu = types.InlineKeyboardButton('📋 Меню', callback_data='menu')
            markup.add(btn_back, btn_menu)
            
            text = f"✅ *Покупка успешна!*\n\n🪱 Куплено: {bait_name}\n💰 Потрачено: {bait['price']} {COINS_NAME}\n💳 Осталось: {new_balance} {COINS_NAME}\n\nПриманка добавлена в инвентарь!"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка покупки!")
    
    elif call.data.startswith('buy_rod_'):
        rod_name = call.data[8:]
        rod = next((r for r in RODS if r['name'] == rod_name), None)
        
        if not rod:
            bot.answer_callback_query(call.id, "❌ Удочка не найдена!")
            return
        
        user_data = db.get_user(user.id)
        
        # Проверяем, есть ли уже такая удочка
        has_rod = any(r['name'] == rod_name for r in user_data['inventory']['rods'])
        
        if user_data['coins'] < rod['price']:
            bot.answer_callback_query(call.id, f"❌ Недостаточно {COINS_NAME}! Нужно {rod['price']}, у вас {user_data['coins']}")
            return
        
        success, new_balance = db.remove_coins(user.id, rod['price'])
        if success:
            db.add_rod(user.id, rod_name)
            db.update_quest_progress(user.id, "buy_rod")
            db.log_action(user.id, "buy_rod", rod_name)
            
            # Обновляем сообщение
            markup = types.InlineKeyboardMarkup()
            if not has_rod:
                btn_equip = types.InlineKeyboardButton('⚡ Экипировать', callback_data=f'equip_rod_{rod_name}')
                markup.add(btn_equip)
            
            btn_back = types.InlineKeyboardButton('🛒 Продолжить покупки', callback_data='shop_rods')
            btn_menu = types.InlineKeyboardButton('📋 Меню', callback_data='menu')
            markup.add(btn_back, btn_menu)
            
            status = " (у вас уже была такая)" if has_rod else ""
            text = f"✅ *Покупка успешна!*\n\n🎣 Куплено: {rod_name}{status}\n💰 Потрачено: {rod['price']} {COINS_NAME}\n💳 Осталось: {new_balance} {COINS_NAME}\n\nУдочка добавлена в инвентарь!"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка покупки!")
    
    elif call.data.startswith('equip_rod_'):
        rod_name = call.data[10:]
        db.set_current_rod(user.id, rod_name)
        
        bot.answer_callback_query(call.id, f"✅ Удочка {rod_name} экипирована!")
        
        # Возвращаемся в магазин
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        for rod in RODS:
            btn = types.InlineKeyboardButton(f"{rod['emoji']} {rod['name']} - {rod['price']}р", 
                                           callback_data=f'buy_rod_{rod["name"]}')
            markup.add(btn)
        
        btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='shop_back')
        markup.add(btn_back)
        
        user_data = db.get_user(user.id)
        text = f"🎣 *Магазин удочек*\n\n💰 Ваш баланс: {user_data['coins']} {COINS_NAME}\n🎣 Активная удочка: {rod_name}\n\nВыберите удочку:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data.startswith('buy_worms_'):
        count = int(call.data[10:])
        total_price = count * WORM_PRICE
        
        # Скидка на 10 червяков
        if count == 10:
            total_price = WORM_PRICE * 8
        
        user_data = db.get_user(user.id)
        
        if user_data['worms'] >= MAX_WORMS:
            bot.answer_callback_query(call.id, f"❌ У вас уже максимальное количество червяков ({MAX_WORMS})!")
            return
        
        if user_data['coins'] < total_price:
            bot.answer_callback_query(call.id, f"❌ Недостаточно {COINS_NAME}! Нужно {total_price}, у вас {user_data['coins']}")
            return
        
        # Рассчитываем сколько можно купить
        can_buy = min(count, MAX_WORMS - user_data['worms'])
        if can_buy <= 0:
            bot.answer_callback_query(call.id, f"❌ У вас уже максимальное количество червяков ({MAX_WORMS})!")
            return
        
        actual_price = int(total_price * (can_buy / count))
        
        success, new_balance = db.remove_coins(user.id, actual_price)
        if success:
            user_data['worms'] = min(user_data['worms'] + can_buy, MAX_WORMS)
            db.save_data()
            db.update_quest_progress(user.id, "buy_bait")
            db.log_action(user.id, "buy_worms", f"{can_buy} шт за {actual_price}")
            
            # Обновляем сообщение
            markup = types.InlineKeyboardMarkup()
            btn_back = types.InlineKeyboardButton('🛒 Продолжить покупки', callback_data='shop_worms')
            btn_menu = types.InlineKeyboardButton('📋 Меню', callback_data='menu')
            markup.add(btn_back, btn_menu)
            
            text = f"✅ *Покупка успешна!*\n\n🐛 Куплено: {can_buy} червяков\n💰 Потрачено: {actual_price} {COINS_NAME}\n💳 Осталось: {new_balance} {COINS_NAME}\n📦 Всего червяков: {user_data['worms']}/10"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка покупки!")
    
    elif call.data.startswith('sell_npc_'):
        npc_index = int(call.data[9:])
        npc = NPC_SELLERS[npc_index]
        
        user_data = db.get_user(user.id)
        
        if not user_data['inventory']['fish']:
            bot.answer_callback_query(call.id, "❌ У вас нет рыбы для продажи!")
            return
        
        # Создаем клавиатуру для выбора рыбы
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        for fish_name, count in user_data['inventory']['fish'].items():
            # Находим базовую цену
            base_price = 0
            for fish in FISHES:
                if fish['name'] == fish_name:
                    base_price = fish.get('price', 0)
                    break
            
            if base_price > 0:
                total_price = int(base_price * npc['multiplier'])
                btn = types.InlineKeyboardButton(f"{fish_name} ({count}шт) - {total_price}р", 
                                               callback_data=f'sell_fish_{npc_index}_{fish_name}_1')
                markup.add(btn)
        
        # Кнопки для продажи всего
        for fish_name, count in user_data['inventory']['fish'].items():
            base_price = 0
            for fish in FISHES:
                if fish['name'] == fish_name:
                    base_price = fish.get('price', 0)
                    break
            
            if base_price > 0 and count > 1:
                total_price = int(base_price * count * npc['multiplier'])
                btn = types.InlineKeyboardButton(f"ВСЁ {fish_name} ({count}шт) - {total_price}р", 
                                               callback_data=f'sell_fish_{npc_index}_{fish_name}_{count}')
                markup.add(btn)
        
        btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='sell_back')
        markup.add(btn_back)
        
        text = f"💰 *Продажа рыбы*\n\n{npc['emoji']} *{npc['name']}*\n{npc['description']}\n📈 Множитель цены: x{npc['multiplier']}\n\nВыберите рыбу для продажи:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data == 'sell_back':
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        for i, npc in enumerate(NPC_SELLERS):
            btn = types.InlineKeyboardButton(f"{npc['emoji']} {npc['name']}", callback_data=f'sell_npc_{i}')
            markup.add(btn)
        
        btn_back = types.InlineKeyboardButton('📋 Меню', callback_data='menu')
        markup.add(btn_back)
        
        user_data = db.get_user(user.id)
        text = f"💰 *Продажа рыбы*\n\n🐟 Ваша рыба:\n"
        
        for fish_name, count in user_data['inventory']['fish'].items():
            base_price = 0
            for fish in FISHES:
                if fish['name'] == fish_name:
                    base_price = fish.get('price', 0)
                    break
            
            if base_price > 0:
                text += f"• {fish_name}: {count} шт (по {base_price} {COINS_NAME})\n"
        
        text += "\nВыберите покупателя:"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
    
    elif call.data.startswith('sell_fish_'):
        parts = call.data.split('_')
        npc_index = int(parts[2])
        fish_name = parts[3]
        count = int(parts[4])
        
        npc = NPC_SELLERS[npc_index]
        user_data = db.get_user(user.id)
        
        # Проверяем, есть ли рыба
        if fish_name not in user_data['inventory']['fish'] or user_data['inventory']['fish'][fish_name] < count:
            bot.answer_callback_query(call.id, "❌ Недостаточно рыбы!")
            return
        
        # Находим цену
        base_price = 0
        for fish in FISHES:
            if fish['name'] == fish_name:
                base_price = fish.get('price', 0)
                break
        
        if base_price == 0:
            bot.answer_callback_query(call.id, "❌ Ошибка определения цены!")
            return
        
        total_price = int(base_price * count * npc['multiplier'])
        
        # Продаем
        success, earned = db.sell_fish(user.id, fish_name, count, npc['multiplier'])
        
        if success:
            db.update_quest_progress(user.id, "sell", earned)
            db.log_action(user.id, "sell_fish", f"{fish_name} x{count} за {earned}")
            
            # Обновляем сообщение
            markup = types.InlineKeyboardMarkup()
            btn_more = types.InlineKeyboardButton('💰 Продать еще', callback_data=f'sell_npc_{npc_index}')
            btn_menu = types.InlineKeyboardButton('📋 Меню', callback_data='menu')
            markup.add(btn_more, btn_menu)
            
            text = f"💰 *Продажа успешна!*\n\n{npc['emoji']} {npc['name']}\n🐟 Продано: {fish_name} x{count}\n💵 Получено: {earned} {COINS_NAME}\n💳 Всего: {user_data['coins']} {COINS_NAME}\n\n{npc['description']}"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)
        else:
            bot.answer_callback_query(call.id, "❌ Ошибка продажи!")

# ========== ОБРАБОТКА ВСЕХ СООБЩЕНИЙ ==========
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_messages(message):
    delete_links_in_group(message)
    
    text = message.text
    if text in ['🎣 Начать рыбалку', '📊 Статистика', '🎒 Инвентарь', '❓ Помощь', '🎣 Забросить удочку', '📋 Меню', 
                '🛒 Магазин', '💰 Продать рыбу', '📜 Задания', '👑 Админ панель', '🚫 Бан/Разбан', '📋 Список админов',
                '📜 Логи банов', '🎣 Выдать предметы', '💰 Выдать монеты', '👤 Статистика игрока', '⚙️ Полное управление',
                '🗑️ Очистить логи']:
        return
    if text and text.startswith('/'):
        return

@bot.message_handler(content_types=['photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle_media_messages(message):
    delete_links_in_group(message)

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
    return "🎣 Fishing Bot is running! Use /set_webhook to configure", 200

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    """Установка webhook (вызовите этот URL один раз)"""
    if not WEBHOOK_URL:
        return "❌ RENDER_EXTERNAL_URL не настроен", 500
    
    try:
        # Удаляем старый webhook
        bot.remove_webhook()
        time.sleep(0.1)
        
        # Устанавливаем новый с ВСЕМИ типами обновлений
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
    """Удаление webhook (если нужно перейти на polling)"""
    try:
        bot.remove_webhook()
        return "✅ Webhook удален", 200
    except Exception as e:
        return f"❌ Ошибка: {str(e)}", 500

@app.route('/health')
def health():
    """Эндпоинт для проверки здоровья и keep-alive"""
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
            "admins_count": len(ADMINS),
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
if __name__ == '__main__':
    print("=" * 50)
    print("🎣 Fishing Bot Webhook Edition")
    print(f"✅ Webhook URL: {WEBHOOK_URL if WEBHOOK_URL else 'Не настроен'}")
    print("=" * 50)
    
    try:
        # Получаем информацию о боте
        bot_info = bot.get_me()
        print(f"✅ Бот загружен: @{bot_info.username} ({bot_info.first_name})")
    except Exception as e:
        print(f"❌ Ошибка загрузки бота: {e}")
    
    print(f"👑 Админы: {len(ADMINS)} пользователей")
    print(f"🐟 Рыб: {len(FISHES)} видов")
    print(f"🪱 Приманок: {len(BAITS)} видов")
    print(f"🎣 Удочек: {len(RODS)} видов")
    
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
