#!/usr/bin/env python3
# bot_fish_complete.py - Полный бот со всеми функциями
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
import math

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

# Настройки игры (СТАРЫЕ - БЕЗ ИЗМЕНЕНИЙ!)
INITIAL_WORMS = 10
MAX_WORMS = 10
FISHING_TIME = 30
WORM_REFILL_TIME = 900  # 15 минут
WARNING_EXPIRE_TIME = 86400  # 24 часа
BAN_DURATION = 172800  # 2 дня

# Список администраторов
ADMIN_IDS = [8351629145, 5330661807, 7093049365]

# Цены на донат (уникальные для идентификации)
DONATE_PRICES = {
    99: "🐛 Пакет наживки (10шт каждого вида)",
    199: "🎣 Улучшение удачи +10% (7 дней)",
    200: "🎣 Улучшение удачи +20% (30 дней)",
    299: "🔧 Улучшение удочки (не ломается навсегда)",
    499: "🎣 Спиннинг Pro (удача +30%)",
    999: "💰 1000 Рыбоп",
    1999: "💰 2500 Рыбоп + сундук",
    2999: "💰 5000 Рыбоп + сундук + улучшение",
    4999: "💰 10000 Рыбоп + всё максимальное"
}

# Банковские реквизиты
BANK_CARD = "2200702034105283"  # Тинькофф

# Список рыб (30 видов) - СТАРЫЕ - БЕЗ ИЗМЕНЕНИЙ!
FISHES_OLD = [
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

# НОВАЯ РЫБА (100 видов) с точными весами
FISHES_NEW = []
fish_base = [
    ("Щука обыкновенная", "хищная", 1000, 15000),
    ("Окунь речной", "хищная", 100, 2000),
    ("Карась серебряный", "мирная", 200, 1500),
    ("Карась золотой", "мирная", 300, 2000),
    ("Лещ", "мирная", 500, 6000),
    ("Плотва", "мирная", 100, 1000),
    ("Густера", "мирная", 200, 1200),
    ("Ёрш", "хищная", 50, 300),
    ("Налим", "хищная", 500, 18000),
    ("Язь", "мирная", 300, 4000),
    ("Голавль", "хищная", 200, 4000),
    ("Жерех", "хищная", 500, 8000),
    ("Сазан", "мирная", 1000, 20000),
    ("Карп", "мирная", 1000, 25000),
    ("Линь", "мирная", 300, 4000),
    ("Пескарь", "мирная", 20, 150),
    ("Уклейка", "мирная", 10, 100),
    ("Быстрянка", "мирная", 10, 80),
    ("Голец", "мирная", 20, 100),
    ("Вьюн", "мирная", 50, 200),
    ("Сом", "хищная", 5000, 100000),
    ("Судак", "хищная", 800, 12000),
    ("Берш", "хищная", 300, 3000),
    ("Чоп", "хищная", 200, 2000),
    ("Минога", "хищная", 100, 1000),
    ("Хариус", "хищная", 200, 2500),
    ("Таймень", "хищная", 3000, 40000),
    ("Ленок", "хищная", 500, 6000),
    ("Форель ручьевая", "хищная", 200, 2000),
    ("Голец арктический", "хищная", 500, 10000),
    ("Сиг", "хищная", 300, 5000),
    ("Чир", "хищная", 500, 8000),
    ("Пелядь", "хищная", 300, 4000),
    ("Омуль", "хищная", 400, 5000),
    ("Муксун", "хищная", 500, 8000),
    ("Нельма", "хищная", 1000, 15000),
    ("Ряпушка", "хищная", 50, 200),
    ("Корюшка", "хищная", 20, 150),
    ("Снеток", "хищная", 10, 80),
    ("Ротан", "хищная", 50, 500),
    ("Подкаменщик", "хищная", 20, 150),
    ("Бычок-кругляк", "хищная", 50, 300),
    ("Бычок-песочник", "хищная", 30, 200),
    ("Амур белый", "мирная", 1000, 25000),
    ("Толстолобик", "мирная", 2000, 35000),
    ("Змееголов", "хищная", 1000, 8000),
    ("Верхогляд", "хищная", 500, 10000),
    ("Желтощёк", "хищная", 1000, 15000),
    ("Конь-губарь", "мирная", 300, 2000),
    ("Подуст", "мирная", 200, 1500),
    ("Елец", "мирная", 50, 300),
    ("Синец", "мирная", 200, 1000),
    ("Белоглазка", "мирная", 200, 1000),
    ("Краснопёрка", "мирная", 100, 1000),
    ("Горчак", "мирная", 20, 80),
    ("Верховка", "мирная", 5, 30),
    ("Чехонь", "хищная", 200, 1500),
    ("Атерина", "хищная", 20, 100),
    ("Игла-рыба", "хищная", 50, 300),
    ("Звездчатая камбала", "хищная", 200, 3000),
    ("Речная камбала", "хищная", 300, 4000),
    ("Палтус", "хищная", 5000, 100000),
    ("Треска", "хищная", 1000, 25000),
    ("Пикша", "хищная", 500, 15000),
    ("Сайда", "хищная", 500, 10000),
    ("Мерланг", "хищная", 300, 2000),
    ("Мойва", "хищная", 20, 50),
    ("Сельдь атлантическая", "хищная", 200, 800),
    ("Сельдь тихоокеанская", "хищная", 200, 800),
    ("Килька", "хищная", 10, 30),
    ("Сардина", "хищная", 100, 300),
    ("Анчоус", "хищная", 20, 50),
    ("Ставрида", "хищная", 100, 1000),
    ("Скумбрия", "хищная", 300, 2000),
    ("Тунец", "хищная", 10000, 200000),
    ("Меч-рыба", "хищная", 50000, 400000),
    ("Марлин", "хищная", 40000, 300000),
    ("Королевская макрель", "хищная", 5000, 40000),
    ("Барракуда", "хищная", 3000, 20000),
    ("Рыба-меч", "хищная", 30000, 250000),
    ("Луфарь", "хищная", 1000, 10000),
    ("Горбыль", "хищная", 500, 8000),
    ("Морской окунь", "хищная", 300, 5000),
    ("Терпуг", "хищная", 500, 6000),
    ("Зубан", "хищная", 800, 12000),
    ("Каменный окунь", "хищная", 200, 3000),
    ("Сарган", "хищная", 300, 1500),
    ("Кефаль", "мирная", 300, 4000),
    ("Пеламида", "хищная", 1000, 15000),
    ("Бонито", "хищная", 2000, 20000),
    ("Ваху", "хищная", 5000, 40000),
    ("Дорадо", "хищная", 1000, 12000),
    ("Сибас", "хищная", 1000, 10000),
    ("Камбала-ёрш", "хищная", 500, 7000),
    ("Палтус черный", "хищная", 10000, 100000),
    ("Палтус синекорый", "хищная", 20000, 200000),
    ("Треска арктическая", "хищная", 2000, 30000),
    ("Сайка", "хищная", 100, 300),
    ("Морская щука", "хищная", 1000, 15000),
    ("Скорпена", "хищная", 300, 3000),
    ("Морской чёрт", "хищная", 5000, 40000),
    ("Скат", "хищная", 3000, 50000),
    ("Акула катран", "хищная", 5000, 15000),
    ("Акула сельдевая", "хищная", 20000, 100000),
    ("Акула голубая", "хищная", 50000, 200000),
]

# Генерируем новую рыбу с точными весами
for i, (name, fish_type, min_weight, max_weight) in enumerate(fish_base[:100]):
    if max_weight >= 50000:
        rarity = "легендарная"
    elif max_weight >= 10000:
        rarity = "эпическая"
    elif max_weight >= 5000:
        rarity = "редкая"
    elif max_weight >= 1000:
        rarity = "необычная"
    else:
        rarity = "обычная"
    
    FISHES_NEW.append({
        "id": i + 100,  # Начинаем с 100 чтобы не пересекаться со старой рыбой
        "name": name,
        "type": fish_type,
        "rarity": rarity,
        "min_weight": min_weight,
        "max_weight": max_weight,
        "emoji": "🐟" if fish_type == "мирная" else "🦈",
        "price_per_kg": random.randint(50, 500)
    })

# Объединяем старую и новую рыбу
ALL_FISHES = FISHES_OLD + FISHES_NEW

# Редкости и их вероятности - СТАРЫЕ - БЕЗ ИЗМЕНЕНИЙ!
RARITY_PROBABILITIES = {
    "обычная": 50,
    "редкая": 30,
    "эпическая": 15,
    "легендарная": 4,
    "мусор": 1
}

# Регулярные выражения - СТАРЫЕ - БЕЗ ИЗМЕНЕНИЙ!
URL_PATTERN = re.compile(
    r'(https?://[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9-]+\.(com|ru|net|org|info|io|me|tv|co|us|uk|de|fr|es|it|jp|cn|рф)[^\s]*)|(t\.me/[^\s]+)|(telegram\.me/[^\s]+)|(tg://[^\s]+)'
)
USERNAME_PATTERN = re.compile(r'@[a-zA-Z0-9_]{5,32}')

# ========== РЫБНЫЕ МЕСТНОСТИ (10 водоемов) ==========
FISHING_LOCATIONS = [
    {
        "id": 1,
        "name": "🌊 Волга",
        "description": "Крупнейшая река Европы",
        "depth": "глубоководная",
        "fish_types": ["щука", "судак", "сом", "лещ", "плотва", "окунь", "жерех", "сазан", "голавль", "язь"]
    },
    {
        "id": 2,
        "name": "🏔️ Байкал",
        "description": "Самое глубокое озеро мира",
        "depth": "очень глубокая",
        "fish_types": ["омуль", "хариус", "сиг", "таймень", "налим", "окунь", "щука", "елец", "плотва", "голец"]
    },
    {
        "id": 3,
        "name": "🌅 Ладожское озеро",
        "description": "Крупнейшее озеро Европы",
        "depth": "средняя",
        "fish_types": ["лосось", "сиг", "ряпушка", "судак", "лещ", "плотва", "окунь", "щука", "налим", "корюшка"]
    },
    {
        "id": 4,
        "name": "❄️ Енисей",
        "description": "Одна из крупнейших рек России",
        "depth": "глубокая",
        "fish_types": ["осётр", "стерлядь", "таймень", "ленок", "хариус", "налим", "щука", "окунь", "язь", "плотва"]
    },
    {
        "id": 5,
        "name": "🌲 Онежское озеро",
        "description": "Второе по величине озеро Европы",
        "depth": "средняя",
        "fish_types": ["лосось", "палия", "сиг", "ряпушка", "лещ", "судак", "щука", "окунь", "плотва", "налим"]
    },
    {
        "id": 6,
        "name": "🏞️ Амур",
        "description": "Река на Дальнем Востоке",
        "depth": "переменная",
        "fish_types": ["калуга", "осётр", "сазан", "щука", "сом", "желтощёк", "верхогляд", "конь-губарь", "пескарь", "амур"]
    },
    {
        "id": 7,
        "name": "🌊 Чёрное море",
        "description": "Тёплое море на юге",
        "depth": "морская",
        "fish_types": ["ставрида", "камбала", "кефаль", "бычок", "морской окунь", "скумбрия", "сельдь", "скат", "мерланг", "лосось"]
    },
    {
        "id": 8,
        "name": "❄️ Обь",
        "description": "Река в Сибири",
        "depth": "широкая",
        "fish_types": ["нельма", "муксун", "пелядь", "чир", "окунь", "щука", "язь", "плотва", "лещ", "налим"]
    },
    {
        "id": 9,
        "name": "🏔️ Телецкое озеро",
        "description": "Горное озеро на Алтае",
        "depth": "глубокая",
        "fish_types": ["таймень", "ленок", "хариус", "сиг", "налим", "окунь", "плотва", "елец", "подкаменщик", "голец"]
    },
    {
        "id": 10,
        "name": "🌅 Каспийское море",
        "description": "Крупнейший замкнутый водоём",
        "depth": "морская",
        "fish_types": ["осётр", "севрюга", "белуга", "сельдь", "килька", "вобла", "лещ", "сазан", "судак", "сом"]
    }
]

# ========== НАЖИВКИ с эмодзи ==========
BAITS = {
    "red_oparysh": {
        "name": "🔴 Красный опарыш",
        "price": 50,  # в рыбопах
        "effectiveness": {"щука": 0.1, "окунь": 0.3, "плотва": 0.4, "лещ": 0.5, "карась": 0.6},
        "emoji": "🔴"
    },
    "white_oparysh": {
        "name": "⚪ Белый опарыш",
        "price": 30,
        "effectiveness": {"карась": 0.7, "плотва": 0.5, "лещ": 0.4, "окунь": 0.2, "густера": 0.3},
        "emoji": "⚪"
    },
    "motyl": {
        "name": "🪱 Мотыль",
        "price": 100,
        "effectiveness": {"лещ": 0.8, "плотва": 0.6, "окунь": 0.4, "карась": 0.5, "густера": 0.7},
        "emoji": "🪱"
    },
    "earthworm": {
        "name": "🪱 Дождевой червь",
        "price": 20,
        "effectiveness": {"сом": 0.6, "налим": 0.5, "язь": 0.4, "голавль": 0.3, "окунь": 0.2},
        "emoji": "🪱"
    },
    "manure_worm": {
        "name": "🪱 Навозный червь",
        "price": 40,
        "effectiveness": {"карась": 0.8, "плотва": 0.6, "лещ": 0.5, "линь": 0.4, "окунек": 0.3},
        "emoji": "🪱"
    },
    "simple_worm": {
        "name": "🐛 Обычный червь",
        "price": 0,  # бесплатный
        "effectiveness": {"плотва": 0.3, "окунь": 0.2, "карась": 0.4, "ерш": 0.5, "пескарь": 0.6},
        "emoji": "🐛"
    },
    "bread": {
        "name": "🍞 Хлеб",
        "price": 10,
        "effectiveness": {"карась": 0.9, "плотва": 0.7, "лещ": 0.6, "густера": 0.5, "уклейка": 0.8},
        "emoji": "🍞"
    },
    "corn": {
        "name": "🌽 Кукуруза",
        "price": 25,
        "effectiveness": {"карп": 0.8, "сазан": 0.7, "лещ": 0.5, "карась": 0.6, "плотва": 0.4},
        "emoji": "🌽"
    },
    "dough": {
        "name": "🥣 Тесто",
        "price": 15,
        "effectiveness": {"карась": 0.7, "плотва": 0.6, "лещ": 0.5, "густера": 0.4, "уклейка": 0.9},
        "emoji": "🥣"
    },
    "worm_bundle": {
        "name": "🪱 Пучок червей",
        "price": 80,
        "effectiveness": {"сом": 0.9, "налим": 0.8, "язь": 0.7, "голавль": 0.6, "жерех": 0.5},
        "emoji": "🪱"
    }
}

# ========== УДОЧКИ ==========
RODS = {
    "simple": {
        "name": "🎣 Простая удочка",
        "price": 0,
        "luck": 0.0,
        "durability": 50,
        "max_weight": 2.0,
        "category": "поплавочная",
        "break_chance": 0.1,
        "emoji": "🎣"
    },
    "float": {
        "name": "🎣 Поплавочная удочка",
        "price": 500,
        "luck": 0.05,
        "durability": 100,
        "max_weight": 3.0,
        "category": "поплавочная",
        "break_chance": 0.08,
        "emoji": "🎣"
    },
    "spinning": {
        "name": "🎣 Спиннинг обычный",
        "price": 1500,
        "luck": 0.1,
        "durability": 150,
        "max_weight": 5.0,
        "category": "спиннинг",
        "break_chance": 0.06,
        "emoji": "🎣"
    },
    "spinning_pro": {
        "name": "🎣 Спиннинг Pro",
        "price": 5000,
        "luck": 0.3,
        "durability": 300,
        "max_weight": 10.0,
        "category": "спиннинг",
        "break_chance": 0.03,
        "emoji": "🎣"
    },
    "winter": {
        "name": "⛸️ Зимняя удочка",
        "price": 800,
        "luck": 0.0,
        "durability": 80,
        "max_weight": 1.5,
        "category": "зимняя",
        "break_chance": 0.12,
        "emoji": "⛸️"
    },
    "feeder": {
        "name": "🎣 Фидерная удочка",
        "price": 2000,
        "luck": 0.15,
        "durability": 200,
        "max_weight": 6.0,
        "category": "донная",
        "break_chance": 0.05,
        "emoji": "🎣"
    },
    "carp": {
        "name": "🐟 Карповая удочка",
        "price": 3000,
        "luck": 0.2,
        "durability": 250,
        "max_weight": 15.0,
        "category": "карповая",
        "break_chance": 0.04,
        "emoji": "🐟"
    },
    "sea": {
        "name": "🌊 Морская удочка",
        "price": 6000,
        "luck": 0.25,
        "durability": 400,
        "max_weight": 25.0,
        "category": "морская",
        "break_chance": 0.02,
        "emoji": "🌊"
    },
    "telescopic": {
        "name": "🔭 Телескопическая удочка",
        "price": 1200,
        "luck": 0.08,
        "durability": 120,
        "max_weight": 4.0,
        "category": "универсальная",
        "break_chance": 0.07,
        "emoji": "🔭"
    },
    "match": {
        "name": "🎣 Матчевая удочка",
        "price": 1800,
        "luck": 0.12,
        "durability": 180,
        "max_weight": 5.0,
        "category": "поплавочная",
        "break_chance": 0.06,
        "emoji": "🎣"
    },
    "fly": {
        "name": "🪰 Нахлыстовая удочка",
        "price": 2500,
        "luck": 0.18,
        "durability": 150,
        "max_weight": 3.0,
        "category": "нахлыст",
        "break_chance": 0.09,
        "emoji": "🪰"
    }
}

# ========== USER DATABASE (ОБНОВЛЕННЫЙ) ==========
class UserDatabase:
    def __init__(self):
        self.users = {}
        self.active_fishing = {}
        self.news = []
        self.logs = []
        self.donate_transactions = []
        self.load_data()
    
    def load_data(self):
        """Загружаем данные из файлов"""
        try:
            with open('users_data_complete.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.users = data.get('users', {})
                self.news = data.get('news', [])
                self.logs = data.get('logs', [])
                self.donate_transactions = data.get('donate_transactions', [])
            print(f"✅ Загружено {len(self.users)} пользователей")
            
            # Конвертируем старые данные в новый формат
            self.convert_old_data()
            
        except FileNotFoundError:
            print("📁 Файл данных не найден, начинаем с чистого листа")
            self.users = {}
            self.news = []
            self.logs = []
            self.donate_transactions = []
        except Exception as e:
            print(f"⚠️ Ошибка загрузки данных: {e}")
            self.users = {}
            self.news = []
            self.logs = []
            self.donate_transactions = []
    
    def convert_old_data(self):
        """Конвертируем старые данные в новый формат"""
        converted = 0
        for user_id, user_data in self.users.items():
            # Если у пользователя есть worms, значит это старый формат
            if 'worms' in user_data:
                # Конвертируем в новый формат
                user_data['baits'] = {
                    'simple_worm': user_data.get('worms', INITIAL_WORMS),
                    'red_oparysh': 0,
                    'white_oparysh': 0,
                    'motyl': 0,
                    'earthworm': 0,
                    'manure_worm': 0
                }
                user_data['money'] = user_data.get('money', 100)
                user_data['rods'] = ['simple']
                user_data['active_rod'] = 'simple'
                user_data['rod_durability'] = {'simple': 50}
                user_data['location'] = 1
                user_data['level'] = 1
                user_data['exp'] = 0
                user_data['luck_boost'] = 0
                user_data['unbreakable_rod'] = False
                user_data['admin_level'] = 5 if int(user_id) in ADMIN_IDS else 0
                user_data['daily_tasks'] = {}
                user_data['achievements'] = []
                converted += 1
        
        if converted > 0:
            self.save_data()
            print(f"🔄 Конвертировано {converted} пользователей в новый формат")
    
    def save_data(self):
        """Сохраняем данные в файл"""
        try:
            data = {
                'users': self.users,
                'news': self.news,
                'logs': self.logs,
                'donate_transactions': self.donate_transactions,
                'last_save': datetime.now().isoformat()
            }
            with open('users_data_complete.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, default=str)
            print(f"💾 Данные сохранены ({len(self.users)} пользователей)")
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    
    def log_action(self, user_id, action, details):
        """Логируем действие"""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'action': action,
            'details': details
        }
        self.logs.append(log_entry)
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
    
    def add_donate_transaction(self, user_id, amount, item, screenshot=None):
        """Добавляем транзакцию доната"""
        transaction = {
            'id': len(self.donate_transactions) + 1,
            'user_id': user_id,
            'amount': amount,
            'item': item,
            'screenshot': screenshot,
            'timestamp': datetime.now().isoformat(),
            'processed': False
        }
        self.donate_transactions.append(transaction)
        self.save_data()
        return transaction['id']
    
    # ========== СТАРЫЕ МЕТОДЫ (БЕЗ ИЗМЕНЕНИЙ) ==========
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            # Создаем пользователя в старом формате
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
        
        user = self.users[user_id]
        
        # Автопополнение червяков (старая система)
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
            self.save_data()
            return True, user['worms']
        return False, user['worms']
    
    def add_fish(self, user_id, fish):
        user = self.get_user(user_id)
        
        # Генерируем точный вес для новой рыбы
        if isinstance(fish, dict) and 'min_weight' in fish:
            exact_weight = random.randint(fish['min_weight'], fish['max_weight'])
            weight_display = f"{exact_weight}г"
        else:
            # Для старой рыбы используем диапазон
            weight_display = fish['weight']
        
        catch = {
            'fish': fish['name'],
            'rarity': fish['rarity'],
            'weight': weight_display,
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
    
    # ========== НОВЫЕ МЕТОДЫ ==========
    def get_user_new(self, user_id):
        """Получаем пользователя в новом формате"""
        user = self.get_user(user_id)
        
        # Добавляем новые поля если их нет
        if 'baits' not in user:
            user['baits'] = {
                'simple_worm': user.get('worms', INITIAL_WORMS),
                'red_oparysh': 0,
                'white_oparysh': 0,
                'motyl': 0,
                'earthworm': 0,
                'manure_worm': 0,
                'bread': 0,
                'corn': 0,
                'dough': 0,
                'worm_bundle': 0
            }
        
        if 'money' not in user:
            user['money'] = 100
        
        if 'rods' not in user:
            user['rods'] = ['simple']
        
        if 'active_rod' not in user:
            user['active_rod'] = 'simple'
        
        if 'rod_durability' not in user:
            user['rod_durability'] = {'simple': 50}
        
        if 'location' not in user:
            user['location'] = 1
        
        if 'level' not in user:
            user['level'] = 1
        
        if 'exp' not in user:
            user['exp'] = 0
        
        if 'luck_boost' not in user:
            user['luck_boost'] = 0
        
        if 'unbreakable_rod' not in user:
            user['unbreakable_rod'] = False
        
        if 'admin_level' not in user:
            user['admin_level'] = 5 if int(user_id) in ADMIN_IDS else 0
        
        if 'daily_tasks' not in user:
            user['daily_tasks'] = {}
        
        if 'achievements' not in user:
            user['achievements'] = []
        
        return user
    
    def get_all_users(self):
        """Получаем список всех пользователей"""
        return list(self.users.values())
    
    def get_top_users(self, criteria='total_fish', limit=10):
        """Топ пользователей по критерию"""
        users_list = list(self.users.values())
        
        if criteria == 'total_fish':
            users_list.sort(key=lambda x: x.get('total_fish', 0), reverse=True)
        elif criteria == 'money':
            users_list.sort(key=lambda x: x.get('money', 0), reverse=True)
        elif criteria == 'legendary':
            users_list.sort(key=lambda x: x.get('stats', {}).get('legendary', 0), reverse=True)
        elif criteria == 'level':
            users_list.sort(key=lambda x: x.get('level', 1), reverse=True)
        
        return users_list[:limit]
    
    def add_news(self, title, content, author_id):
        """Добавляем новость"""
        news_item = {
            'id': len(self.news) + 1,
            'title': title,
            'content': content,
            'author_id': author_id,
            'timestamp': datetime.now().isoformat(),
            'sent_to_all': False
        }
        self.news.append(news_item)
        self.save_data()
        return news_item
    
    def get_unread_news(self, user_id):
        """Получаем непрочитанные новости"""
        user = self.get_user(user_id)
        last_read = user.get('last_news_read', 0)
        return [n for n in self.news if n['id'] > last_read]
    
    def mark_news_as_read(self, user_id):
        """Отмечаем новости как прочитанные"""
        user = self.get_user(user_id)
        if self.news:
            user['last_news_read'] = max([n['id'] for n in self.news])
        self.save_data()
    
    def add_daily_task(self, user_id, task_type, reward):
        """Добавляем ежедневное задание"""
        user = self.get_user(user_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if 'daily_tasks' not in user:
            user['daily_tasks'] = {}
        
        user['daily_tasks'][today] = {
            'type': task_type,
            'progress': 0,
            'target': 3 if task_type == 'catch' else 5,
            'reward': reward,
            'completed': False
        }
        self.save_data()
    
    def complete_daily_task(self, user_id):
        """Завершаем ежедневное задание"""
        user = self.get_user(user_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if 'daily_tasks' in user and today in user['daily_tasks']:
            task = user['daily_tasks'][today]
            if not task['completed']:
                task['completed'] = True
                user['money'] = user.get('money', 0) + task['reward']
                self.save_data()
                return task['reward']
        return 0

db = UserDatabase()

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (СТАРЫЕ - БЕЗ ИЗМЕНЕНИЙ!) ==========
def calculate_catch():
    total_prob = sum(RARITY_PROBABILITIES.values())
    rand_num = random.randint(1, total_prob)
    current_prob = 0
    
    for rarity, prob in RARITY_PROBABILITIES.items():
        current_prob += prob
        if rand_num <= current_prob:
            selected_rarity = rarity
            break
    
    available_fish = [f for f in FISHES_OLD if f['rarity'] == selected_rarity]
    if not available_fish:
        available_fish = [f for f in FISHES_OLD if f['rarity'] == "обычная"]
    
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

# ========== НОВЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def calculate_new_catch(user_data, location_id):
    """Расчет улова с учетом наживки, удочки и местности"""
    if location_id > len(FISHING_LOCATIONS):
        location_id = 1
    
    location = FISHING_LOCATIONS[location_id - 1]
    
    # Выбираем наживку
    available_baits = [bait for bait, count in user_data.get('baits', {}).items() if count > 0]
    if not available_baits:
        return None, None
    
    selected_bait = random.choice(available_baits)
    
    # Определяем вероятность поймать рыбу
    base_probability = 70
    
    # Учет удачи удочки
    rod = RODS.get(user_data.get('active_rod', 'simple'), RODS['simple'])
    rod_luck = rod['luck'] * 100
    
    # Учет буста удачи пользователя
    user_luck = user_data.get('luck_boost', 0)
    
    total_probability = min(base_probability + rod_luck + user_luck, 95)
    
    if random.randint(1, 100) > total_probability:
        return None, selected_bait
    
    # Выбираем рыбу из доступных в локации
    location_fish_names = location['fish_types']
    available_fishes = [f for f in FISHES_NEW if any(fish_name in f['name'].lower() for fish_name in location_fish_names)]
    
    if not available_fishes:
        available_fishes = FISHES_NEW
    
    # Учет эффективности наживки
    bait_info = BAITS.get(selected_bait, BAITS['simple_worm'])
    effectiveness = bait_info.get('effectiveness', {})
    
    # Создаем взвешенный список рыб
    weighted_fishes = []
    for fish in available_fishes:
        weight = 10  # Базовый вес
        
        # Увеличиваем вес, если рыба хорошо ловится на эту наживку
        for fish_type, eff in effectiveness.items():
            if fish_type in fish['name'].lower():
                weight = int(weight * (1 + eff))
                break
        
        weighted_fishes.extend([fish] * weight)
    
    if not weighted_fishes:
        return None, selected_bait
    
    selected_fish = random.choice(weighted_fishes)
    
    # Генерируем точный вес
    exact_weight = random.randint(selected_fish['min_weight'], selected_fish['max_weight'])
    
    # Проверяем, не сломается ли удочка
    weight_kg = exact_weight / 1000
    if weight_kg > rod['max_weight'] and not user_data.get('unbreakable_rod', False):
        # Шанс поломки зависит от превышения веса
        excess = weight_kg - rod['max_weight']
        break_chance = min(rod['break_chance'] * (1 + excess), 0.9)
        
        if random.random() < break_chance:
            # Удочка ломается
            rod_name = rod['name']
            return {
                'fish': None,
                'weight': 0,
                'rod_broken': True,
                'rod_name': rod_name,
                'bait': selected_bait
            }, selected_bait
    
    return {
        'fish': selected_fish,
        'weight': exact_weight,
        'rod_broken': False,
        'bait': selected_bait
    }, selected_bait

def create_advanced_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('🎣 Начать рыбалку')
    btn2 = types.KeyboardButton('📍 Сменить локацию')
    btn3 = types.KeyboardButton('🎒 Инвентарь')
    btn4 = types.KeyboardButton('📊 Статистика')
    btn5 = types.KeyboardButton('🏆 Топы')
    btn6 = types.KeyboardButton('📰 Новости')
    btn7 = types.KeyboardButton('🛒 Магазин')
    btn8 = types.KeyboardButton('💰 Донат')
    btn9 = types.KeyboardButton('❓ Помощь')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8, btn9)
    return markup

def create_admin_keyboard(admin_level):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if admin_level >= 1:
        btn1 = types.KeyboardButton('🎁 Выдать донат')
        btn2 = types.KeyboardButton('📊 Статистика игрока')
        markup.add(btn1, btn2)
    
    if admin_level >= 5:
        btn3 = types.KeyboardButton('📜 Логи действий')
        btn4 = types.KeyboardButton('👥 Список игроков')
        btn5 = types.KeyboardButton('⚡ Выдать предупреждение')
        btn6 = types.KeyboardButton('🚫 Забанить')
        btn7 = types.KeyboardButton('✅ Разбанить')
        btn8 = types.KeyboardButton('📢 Отправить новость')
        btn9 = types.KeyboardButton('🔙 Главное меню')
        markup.add(btn3, btn4, btn5, btn6, btn7, btn8, btn9)
    
    return markup

def create_location_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    for location in FISHING_LOCATIONS:
        btn = types.InlineKeyboardButton(
            location['name'],
            callback_data=f'location_{location["id"]}'
        )
        markup.add(btn)
    return markup

def create_shop_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Наживки
    btn1 = types.InlineKeyboardButton('🐛 Наживки', callback_data='shop_baits')
    # Удочки
    btn2 = types.InlineKeyboardButton('🎣 Удочки', callback_data='shop_rods')
    # Улучшения
    btn3 = types.InlineKeyboardButton('⚡ Улучшения', callback_data='shop_upgrades')
    
    markup.add(btn1, btn2, btn3)
    return markup

def create_donate_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for amount, item in DONATE_PRICES.items():
        btn = types.InlineKeyboardButton(
            f"{item} - {amount}₽",
            callback_data=f"donate_{amount}"
        )
        markup.add(btn)
    
    return markup

def send_news_to_all(news_item):
    """Отправляем новость всем пользователям"""
    news_text = f"📢 *{news_item['title']}*\n\n{news_item['content']}"
    
    for user_id in db.users.keys():
        try:
            bot.send_message(user_id, news_text, parse_mode='Markdown')
        except:
            pass
    
    news_item['sent_to_all'] = True
    db.save_data()

# ========== СТАРЫЕ КОМАНДЫ (БЕЗ ИЗМЕНЕНИЙ) ==========
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
            f"Ожидайте окончания бана для продолжения игры."
        )
        bot.send_message(message.chat.id, ban_text)
        return
    
    # Проверяем админский уровень
    admin_level = 5 if user.id in ADMIN_IDS else 0
    
    if admin_level > 0:
        user_data['admin_level'] = admin_level
        db.save_data()
        welcome_text = f"👑 Привет, администратор {user.first_name}!\nДобро пожаловать в панель управления!"
        bot.send_message(message.chat.id, welcome_text, reply_markup=create_admin_keyboard(admin_level))
    else:
        welcome_text = (
            f"🎣 Привет, {user.first_name}!\n"
            f"Добро пожаловать в мир продвинутой рыбалки!\n\n"
            f"🐛 Червяков: {user_data['worms']}/10\n"
            f"🐟 Всего поймано: {user_data['total_fish']}\n\n"
            f"♻️ Червяки пополняются каждые 15 минут!\n\n"
            f"Используй кнопки ниже для игры!\n\n"
            f"Если хотите поддержать: ||{BANK_CARD}||\n\n"
            f"🎮 *Новые возможности:*\n"
            f"• 10 разных локаций\n"
            • 10 видов наживки\n"
            f"• 11 типов удочек\n"
            f"• 100 видов рыбы\n"
            f"• Магазин и донат\n"
            f"• Система уровней"
        )
        
        bot.send_message(message.chat.id, welcome_text, reply_markup=create_advanced_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['help'])
def help_command(message):
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
        "3️⃣ Червяки восстанавливаются (1 каждые 15 минут)\n"
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
        "🆕 *Новые функции:*\n"
        "• /location - Сменить локацию\n"
        "• /shop - Магазин снастей\n"
        "• /donate - Поддержать проект\n"
        "• /top - Топ игроков\n"
        "• /news - Новости\n\n"
        "Удачи на рыбалке! 🎣"
    )
    
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=create_advanced_keyboard())

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
        f"🎯 Удача: {luck_rate:.1f}% | Мусор: {trash_rate:.1f}%"
    )
    
    # Добавляем новую статистику если есть
    user_data_new = db.get_user_new(user.id)
    if 'money' in user_data_new:
        stats_text += f"\n\n💰 Рыбопов: {user_data_new['money']}"
        stats_text += f"\n🎣 Уровень: {user_data_new.get('level', 1)}"
        stats_text += f"\n📍 Локация: {FISHING_LOCATIONS[user_data_new.get('location', 1)-1]['name']}"
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown', reply_markup=create_advanced_keyboard())

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
    
    bot.send_message(message.chat.id, inventory_text, parse_mode='Markdown', reply_markup=create_advanced_keyboard())

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
                           reply_markup=create_main_keyboard())
        else:
            user_data['worms'] = min(user_data['worms'] + 1, MAX_WORMS)
            user_data['last_worm_refill'] = current_time
            db.save_data()
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
                          reply_markup=create_fishing_keyboard(),
                          parse_mode='Markdown')
    
    def fishing_timer():
        time.sleep(FISHING_TIME)
        
        if user_id in db.active_fishing:
            del db.active_fishing[user_id]
        
        # 50% на старую систему, 50% на новую
        if random.random() < 0.5:
            # Старая система
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
                result_text += "🎊 *ВАУ! Легендарная рыба!* 🎊\n\n"
            elif caught_fish['rarity'] == 'мусор':
                result_text += "😔 Не повезло... Попробуйте еще раз!\n\n"
        else:
            # Новая система
            user_data_new = db.get_user_new(user.id)
            catch_result, bait_used = calculate_new_catch(user_data_new, user_data_new.get('location', 1))
            
            if catch_result is None:
                # Не удалось поймать
                if bait_used in user_data_new['baits']:
                    user_data_new['baits'][bait_used] -= 1
                result_text = (
                    f"😔 *Рыбалка завершена!*\n\n"
                    f"Рыба не клюнула...\n"
                    f"Использована наживка: {BAITS.get(bait_used, {}).get('name', 'Червь')}\n"
                    f"Попробуйте ещё раз!"
                )
            elif catch_result.get('rod_broken'):
                # Удочка сломалась
                if bait_used in user_data_new['baits']:
                    user_data_new['baits'][bait_used] -= 1
                broken_rod = catch_result['rod_name']
                result_text = (
                    f"💔 *Рыбалка завершена!*\n\n"
                    f"О нет! Ваша удочка {broken_rod} сломалась!\n"
                    f"Рыба была слишком тяжелой.\n"
                    f"Купите новую удочку или улучшите текущую!"
                )
            else:
                # Успешный улов
                fish = catch_result['fish']
                weight = catch_result['weight']
                
                if bait_used in user_data_new['baits']:
                    user_data_new['baits'][bait_used] -= 1
                
                # Добавляем рыбу в инвентарь
                catch_record = {
                    'fish': fish['name'],
                    'rarity': fish['rarity'],
                    'weight': f"{weight}г",
                    'emoji': fish['emoji'],
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                # Добавляем в старый инвентарь
                if 'fish_caught' not in user_data_new:
                    user_data_new['fish_caught'] = []
                user_data_new['fish_caught'].append(catch_record)
                if len(user_data_new['fish_caught']) > 20:
                    user_data_new['fish_caught'] = user_data_new['fish_caught'][-20:]
                
                user_data_new['total_fish'] = user_data_new.get('total_fish', 0) + 1
                
                # Обновляем статистику
                if fish['rarity'] == "обычная":
                    user_data_new['stats']['common'] = user_data_new.get('stats', {}).get('common', 0) + 1
                elif fish['rarity'] == "необычная":
                    user_data_new['stats']['rare'] = user_data_new.get('stats', {}).get('rare', 0) + 1
                elif fish['rarity'] == "редкая":
                    user_data_new['stats']['rare'] = user_data_new.get('stats', {}).get('rare', 0) + 1
                elif fish['rarity'] == "эпическая":
                    user_data_new['stats']['epic'] = user_data_new.get('stats', {}).get('epic', 0) + 1
                elif fish['rarity'] == "легендарная":
                    user_data_new['stats']['legendary'] = user_data_new.get('stats', {}).get('legendary', 0) + 1
                
                # Начисляем деньги
                money_earned = int((weight / 1000) * fish['price_per_kg'])
                user_data_new['money'] = user_data_new.get('money', 0) + money_earned
                
                # Добавляем опыт
                exp_gained = 10
                user_data_new['exp'] = user_data_new.get('exp', 0) + exp_gained
                
                # Проверяем уровень
                exp_needed = user_data_new.get('level', 1) * 100
                if user_data_new['exp'] >= exp_needed:
                    user_data_new['level'] = user_data_new.get('level', 1) + 1
                    user_data_new['exp'] = 0
                    user_data_new['money'] += 500
                    level_up_msg = f"\n\n🎊 *Поздравляем! Вы достигли {user_data_new['level']} уровня!* +500 рыбопов"
                else:
                    level_up_msg = ""
                
                # Обновляем основного пользователя
                db.users[str(user.id)] = user_data_new
                db.save_data()
                
                # Формируем сообщение
                rarity_emojis = {
                    'обычная': '🐟',
                    'необычная': '🐠',
                    'редкая': '🌟',
                    'эпическая': '💫',
                    'легендарная': '👑'
                }
                
                result_text = (
                    f"🎉 *Рыбалка завершена!*\n\n"
                    f"{rarity_emojis.get(fish['rarity'], '🎣')} *Поймано:* {fish['name']}\n"
                    f"📊 *Редкость:* {fish['rarity']}\n"
                    f"⚖️ *Вес:* {weight}г ({weight/1000:.2f}кг)\n"
                    f"💰 *Заработано:* {money_earned} рыбопов\n"
                    f"🎣 *Наживка:* {BAITS.get(bait_used, {}).get('name', 'Червь')}\n"
                    f"📈 *Опыт:* +{exp_gained}\n"
                    f"{level_up_msg}"
                )
        
        try:
            bot.send_message(message.chat.id, result_text, parse_mode='Markdown', reply_markup=create_advanced_keyboard())
        except Exception as e:
            print(f"Ошибка отправки: {e}")

    db.active_fishing[user_id] = threading.Thread(target=fishing_timer)
    db.active_fishing[user_id].daemon = True
    db.active_fishing[user_id].start()

# ========== НОВЫЕ КОМАНДЫ ==========
@bot.message_handler(commands=['location'])
def location_command(message):
    bot.send_message(message.chat.id, "Выберите локацию для рыбалки:", reply_markup=create_location_keyboard())

@bot.message_handler(commands=['shop'])
def shop_command(message):
    bot.send_message(message.chat.id, "🛒 Добро пожаловать в магазин! Выберите категорию:", reply_markup=create_shop_keyboard())

@bot.message_handler(commands=['donate'])
def donate_command(message):
    donate_text = (
        "💰 *Поддержать проект*\n\n"
        "Ваша поддержка помогает развивать проект!\n"
        "За донат вы получаете различные бонусы.\n\n"
        "Выберите пакет:"
    )
    bot.send_message(message.chat.id, donate_text, reply_markup=create_donate_keyboard(), parse_mode='Markdown')

@bot.message_handler(commands=['top'])
def top_command(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🐟 По количеству рыбы', callback_data='top_fish')
    btn2 = types.InlineKeyboardButton('💰 По рыбопам', callback_data='top_money')
    btn3 = types.InlineKeyboardButton('👑 По легендарным', callback_data='top_legendary')
    btn4 = types.InlineKeyboardButton('📈 По уровню', callback_data='top_level')
    markup.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(message.chat.id, "Выберите категорию для топа:", reply_markup=markup)

@bot.message_handler(commands=['news'])
def news_command(message):
    user = message.from_user
    unread_news = db.get_unread_news(user.id)
    
    if unread_news:
        for news in unread_news[-5:]:
            news_text = f"📢 *{news['title']}*\n\n{news['content']}\n\n_{news['timestamp'][:10]}_"
            bot.send_message(message.chat.id, news_text, parse_mode='Markdown')
        
        db.mark_news_as_read(user.id)
    else:
        bot.send_message(message.chat.id, "📰 Нет новых новостей. Все актуальные новости вы уже прочитали!", reply_markup=create_advanced_keyboard())

@bot.message_handler(commands=['admin'])
def admin_command(message):
    user = message.from_user
    if user.id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ У вас нет прав администратора!")
        return
    
    admin_level = 5  # Все админы имеют 5 уровень
    user_data = db.get_user(user.id)
    user_data['admin_level'] = admin_level
    db.save_data()
    
    welcome_text = f"👑 Привет, администратор {user.first_name}!\nДобро пожаловать в панель управления!"
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_admin_keyboard(admin_level))

# ========== ОБРАБОТЧИКИ КНОПОК (СТАРЫЕ - БЕЗ ИЗМЕНЕНИЙ!) ==========
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
    bot.send_message(message.chat.id, "Возвращаю в главное меню:", reply_markup=create_advanced_keyboard())

# ========== ОБРАБОТЧИКИ НОВЫХ КНОПОК ==========
@bot.message_handler(func=lambda msg: msg.text == '📍 Сменить локацию')
def location_button_handler(message):
    location_command(message)

@bot.message_handler(func=lambda msg: msg.text == '🏆 Топы')
def top_button_handler(message):
    top_command(message)

@bot.message_handler(func=lambda msg: msg.text == '📰 Новости')
def news_button_handler(message):
    news_command(message)

@bot.message_handler(func=lambda msg: msg.text == '🛒 Магазин')
def shop_button_handler(message):
    shop_command(message)

@bot.message_handler(func=lambda msg: msg.text == '💰 Донат')
def donate_button_handler(message):
    donate_command(message)

@bot.message_handler(func=lambda msg: msg.text == '🔙 Главное меню')
def back_to_menu_handler(message):
    bot.send_message(message.chat.id, "Возвращаю в главное меню:", reply_markup=create_advanced_keyboard())

# ========== АДМИН КНОПКИ ==========
@bot.message_handler(func=lambda msg: db.get_user(msg.from_user.id).get('admin_level', 0) >= 1 and msg.text == '🎁 Выдать донат')
def admin_donate_handler(message):
    msg = bot.send_message(message.chat.id, "Введите ID пользователя и сумму через пробел (пример: 123456789 500):")
    bot.register_next_step_handler(msg, process_donate_gift)

def process_donate_gift(message):
    try:
        parts = message.text.split()
        if len(parts) != 2:
            bot.send_message(message.chat.id, "❌ Неверный формат. Используйте: ID СУММА")
            return
        
        user_id = parts[0]
        amount = int(parts[1])
        
        if amount not in DONATE_PRICES:
            bot.send_message(message.chat.id, f"❌ Неверная сумма. Допустимые суммы: {', '.join(map(str, DONATE_PRICES.keys()))}")
            return
        
        user_data = db.get_user_new(user_id)
        if not user_data:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            return
        
        item = DONATE_PRICES[amount]
        
        # Обрабатываем донат
        if "Пакет наживки" in item:
            for bait in ['red_oparysh', 'white_oparysh', 'motyl', 'earthworm', 'manure_worm', 'bread', 'corn', 'dough', 'worm_bundle']:
                user_data['baits'][bait] = user_data['baits'].get(bait, 0) + 10
        elif "Улучшение удачи" in item:
            if "+10%" in item:
                user_data['luck_boost'] = 10
            elif "+20%" in item:
                user_data['luck_boost'] = 20
        elif "Улучшение удочки" in item:
            user_data['unbreakable_rod'] = True
        elif "Спиннинг Pro" in item:
            if 'spinning_pro' not in user_data['rods']:
                user_data['rods'].append('spinning_pro')
            user_data['active_rod'] = 'spinning_pro'
            user_data['rod_durability']['spinning_pro'] = 300
        elif "Рыбоп" in item:
            if amount == 999:
                user_data['money'] += 1000
            elif amount == 1999:
                user_data['money'] += 2500
            elif amount == 2999:
                user_data['money'] += 5000
                user_data['unbreakable_rod'] = True
            elif amount == 4999:
                user_data['money'] += 10000
                user_data['unbreakable_rod'] = True
                user_data['luck_boost'] = 30
                if 'spinning_pro' not in user_data['rods']:
                    user_data['rods'].append('spinning_pro')
                user_data['active_rod'] = 'spinning_pro'
        
        db.users[user_id] = user_data
        db.save_data()
        db.log_action(message.from_user.id, "выдал донат", f"Пользователю {user_id}: {item}")
        
        # Уведомляем пользователя
        try:
            bot.send_message(user_id, f"🎁 Вам выдан донат: {item}")
        except:
            pass
        
        bot.send_message(message.chat.id, f"✅ Успешно выдано: {item} пользователю {user_id}")
        
    except Exception as e:
        bot.send_message(message.chat.id, f"❌ Ошибка: {str(e)}")

@bot.message_handler(func=lambda msg: db.get_user(msg.from_user.id).get('admin_level', 0) >= 1 and msg.text == '📊 Статистика игрока')
def admin_stats_handler(message):
    msg = bot.send_message(message.chat.id, "Введите ID или @username игрока:")
    bot.register_next_step_handler(msg, process_admin_stats)

def process_admin_stats(message):
    identifier = message.text.strip()
    user_data = None
    
    # Поиск по ID
    if identifier.isdigit():
        user_data = db.get_user(identifier)
    # Поиск по username
    elif identifier.startswith('@'):
        username = identifier[1:].lower()
        for uid, data in db.users.items():
            if data.get('username', '').lower() == username:
                user_data = data
                break
    
    if not user_data:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    stats_text = (
        f"📊 *Статистика игрока*\n\n"
        f"👤 Имя: {user_data.get('first_name', 'Неизвестно')}\n"
        f"📛 Username: @{user_data.get('username', 'нет')}\n"
        f"🆔 ID: {user_data.get('id', identifier)}\n"
        f"🎣 Уровень: {user_data.get('level', 1)}\n"
        f"💰 Рыбопов: {user_data.get('money', 0)}\n"
        f"🐟 Всего рыбы: {user_data.get('total_fish', 0)}\n"
        f"📍 Локация: {FISHING_LOCATIONS[user_data.get('location', 1)-1]['name']}\n"
        f"⚠️ Предупреждений: {len(user_data.get('warnings', []))}\n"
        f"🚫 Забанен: {'Да' if user_data.get('banned_until') else 'Нет'}\n"
        f"👑 Админ уровень: {user_data.get('admin_level', 0)}"
    )
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

# Админ функции 5 уровня
@bot.message_handler(func=lambda msg: db.get_user(msg.from_user.id).get('admin_level', 0) >= 5 and msg.text == '📜 Логи действий')
def admin_logs_handler(message):
    logs = db.logs[-50:]  # Последние 50 логов
    if not logs:
        bot.send_message(message.chat.id, "📜 Логов действий пока нет.")
        return
    
    logs_text = "📜 *Последние действия:*\n\n"
    for log in reversed(logs):
        logs_text += f"⏰ {log['timestamp'][:16]}\n"
        logs_text += f"👤 ID: {log['user_id']}\n"
        logs_text += f"📝 Действие: {log['action']}\n"
        logs_text += f"📋 Детали: {log['details'][:50]}...\n\n"
    
    bot.send_message(message.chat.id, logs_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: db.get_user(msg.from_user.id).get('admin_level', 0) >= 5 and msg.text == '👥 Список игроков')
def admin_users_handler(message):
    users = db.get_all_users()
    if not users:
        bot.send_message(message.chat.id, "👥 Нет зарегистрированных пользователей.")
        return
    
    # Создаем пагинацию
    markup = types.InlineKeyboardMarkup()
    btn1 = types.InlineKeyboardButton("⬅️", callback_data="users_prev_0")
    btn2 = types.InlineKeyboardButton("➡️", callback_data="users_next_0")
    markup.add(btn1, btn2)
    
    users_text = f"👥 *Список игроков (1-10 из {len(users)}):*\n\n"
    for i, user in enumerate(users[:10], 1):
        users_text += f"{i}. {user.get('first_name', 'Неизвестно')} (@{user.get('username', 'нет')})\n"
        users_text += f"   🆔 ID: {user.get('id', 'N/A')}\n"
        users_text += f"   🎣 Уровень: {user.get('level', 1)}\n"
        users_text += f"   🐟 Рыбы: {user.get('total_fish', 0)}\n\n"
    
    bot.send_message(message.chat.id, users_text, parse_mode='Markdown', reply_markup=markup)

@bot.message_handler(func=lambda msg: db.get_user(msg.from_user.id).get('admin_level', 0) >= 5 and msg.text == '⚡ Выдать предупреждение')
def admin_warn_handler(message):
    msg = bot.send_message(message.chat.id, "Введите ID пользователя для выдачи предупреждения:")
    bot.register_next_step_handler(msg, process_admin_warn)

def process_admin_warn(message):
    user_id = message.text.strip()
    user_data = db.get_user(user_id)
    
    if not user_data:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    banned, warning_count, is_ban = db.add_warning(user_id)
    
    if is_ban:
        bot.send_message(message.chat.id, f"✅ Пользователю {user_id} выдано предупреждение и бан на 2 дня!")
    else:
        bot.send_message(message.chat.id, f"✅ Пользователю {user_id} выдано предупреждение. Всего: {warning_count}/2")
    
    db.log_action(message.from_user.id, "выдал предупреждение", f"Пользователю {user_id}, всего: {warning_count}")

@bot.message_handler(func=lambda msg: db.get_user(msg.from_user.id).get('admin_level', 0) >= 5 and msg.text == '🚫 Забанить')
def admin_ban_handler(message):
    msg = bot.send_message(message.chat.id, "Введите ID пользователя для бана:")
    bot.register_next_step_handler(msg, process_admin_ban)

def process_admin_ban(message):
    user_id = message.text.strip()
    user_data = db.get_user(user_id)
    
    if not user_data:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    user_data['banned_until'] = time.time() + BAN_DURATION
    db.save_data()
    
    bot.send_message(message.chat.id, f"✅ Пользователь {user_id} забанен на 2 дня!")
    db.log_action(message.from_user.id, "забанил", f"Пользователя {user_id}")

@bot.message_handler(func=lambda msg: db.get_user(msg.from_user.id).get('admin_level', 0) >= 5 and msg.text == '✅ Разбанить')
def admin_unban_handler(message):
    msg = bot.send_message(message.chat.id, "Введите ID пользователя для разбана:")
    bot.register_next_step_handler(msg, process_admin_unban)

def process_admin_unban(message):
    user_id = message.text.strip()
    user_data = db.get_user(user_id)
    
    if not user_data:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    user_data['banned_until'] = None
    user_data['warnings'] = []
    db.save_data()
    
    bot.send_message(message.chat.id, f"✅ Пользователь {user_id} разбанен и предупреждения сброшены!")
    db.log_action(message.from_user.id, "разбанил", f"Пользователя {user_id}")

@bot.message_handler(func=lambda msg: db.get_user(msg.from_user.id).get('admin_level', 0) >= 5 and msg.text == '📢 Отправить новость')
def admin_news_handler(message):
    msg = bot.send_message(message.chat.id, "Введите заголовок новости:")
    bot.register_next_step_handler(msg, process_admin_news_title)

def process_admin_news_title(message):
    title = message.text
    msg = bot.send_message(message.chat.id, "Введите текст новости:")
    bot.register_next_step_handler(msg, process_admin_news_content, title)

def process_admin_news_content(message, title):
    content = message.text
    news_item = db.add_news(title, content, message.from_user.id)
    send_news_to_all(news_item)
    bot.send_message(message.chat.id, f"✅ Новость отправлена всем пользователям!")
    db.log_action(message.from_user.id, "отправил новость", f"Заголовок: {title}")

# ========== CALLBACK HANDLERS ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user = call.from_user
    user_data = db.get_user_new(user.id)
    
    if call.data.startswith('location_'):
        location_id = int(call.data.split('_')[1])
        user_data['location'] = location_id
        db.users[str(user.id)] = user_data
        db.save_data()
        
        location = FISHING_LOCATIONS[location_id-1]
        bot.edit_message_text(
            f"📍 Локация изменена на: *{location['name']}*\n\n"
            f"📝 {location['description']}\n"
            f"🌊 Тип: {location['depth']}\n"
            f"🐟 Обитает: {', '.join(location['fish_types'][:5])}...",
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
    
    elif call.data == 'shop_baits':
        markup = types.InlineKeyboardMarkup(row_width=2)
        for bait_id, bait_info in BAITS.items():
            if bait_id != 'simple_worm':  # Обычные черви не продаются
                btn = types.InlineKeyboardButton(
                    f"{bait_info['emoji']} {bait_info['name']} - {bait_info['price']} рыбопов",
                    callback_data=f"buy_bait_{bait_id}"
                )
                markup.add(btn)
        
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back")
        markup.add(btn_back)
        
        bot.edit_message_text(
            "🐛 *Магазин наживок*\n\nВыберите наживку для покупки:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    elif call.data.startswith('buy_bait_'):
        bait_id = call.data.split('_')[2]
        bait_info = BAITS[bait_id]
        
        if user_data.get('money', 0) >= bait_info['price']:
            user_data['money'] -= bait_info['price']
            user_data['baits'][bait_id] = user_data['baits'].get(bait_id, 0) + 5
            db.users[str(user.id)] = user_data
            db.save_data()
            
            bot.answer_callback_query(call.id, f"✅ Куплено 5 шт. {bait_info['name']}")
            bot.edit_message_text(
                f"✅ Успешная покупка!\n\n"
                f"Приобретено: 5 шт. {bait_info['name']}\n"
                f"Потрачено: {bait_info['price']} рыбопов\n"
                f"Осталось: {user_data['money']} рыбопов",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "❌ Недостаточно рыбопов!")
    
    elif call.data == 'shop_rods':
        markup = types.InlineKeyboardMarkup(row_width=2)
        for rod_id, rod_info in RODS.items():
            if rod_id != 'simple':  # Простая удочка бесплатная
                btn = types.InlineKeyboardButton(
                    f"{rod_info['emoji']} {rod_info['name']} - {rod_info['price']} рыбопов",
                    callback_data=f"buy_rod_{rod_id}"
                )
                markup.add(btn)
        
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back")
        markup.add(btn_back)
        
        bot.edit_message_text(
            "🎣 *Магазин удочек*\n\nВыберите удочку для покупки:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    elif call.data.startswith('buy_rod_'):
        rod_id = call.data.split('_')[2]
        rod_info = RODS[rod_id]
        
        if user_data.get('money', 0) >= rod_info['price']:
            user_data['money'] -= rod_info['price']
            if rod_id not in user_data['rods']:
                user_data['rods'].append(rod_id)
            user_data['rod_durability'][rod_id] = rod_info['durability']
            db.users[str(user.id)] = user_data
            db.save_data()
            
            bot.answer_callback_query(call.id, f"✅ Куплена {rod_info['name']}")
            bot.edit_message_text(
                f"✅ Успешная покупка!\n\n"
                f"Приобретено: {rod_info['name']}\n"
                f"Потрачено: {rod_info['price']} рыбопов\n"
                f"Осталось: {user_data['money']} рыбопов",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.answer_callback_query(call.id, "❌ Недостаточно рыбопов!")
    
    elif call.data == 'shop_upgrades':
        markup = types.InlineKeyboardMarkup(row_width=2)
        
        upgrades = [
            ("🔧 Улучшение прочности удочки", "Уменьшает шанс поломки на 50%", 1000, "upgrade_durability"),
            ("✨ Улучшение удачи +10% (7 дней)", "Увеличивает удачу на 10%", 1500, "upgrade_luck_10"),
            ("🌟 Улучшение удачи +20% (30 дней)", "Увеличивает удачу на 20%", 3000, "upgrade_luck_20"),
            ("💎 Вечная прочность удочки", "Удочка никогда не ломается", 5000, "upgrade_unbreakable")
        ]
        
        for name, desc, price, callback in upgrades:
            btn = types.InlineKeyboardButton(
                f"{name} - {price} рыбопов",
                callback_data=callback
            )
            markup.add(btn)
        
        btn_back = types.InlineKeyboardButton("🔙 Назад", callback_data="shop_back")
        markup.add(btn_back)
        
        bot.edit_message_text(
            "⚡ *Магазин улучшений*\n\nВыберите улучшение:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup,
            parse_mode='Markdown'
        )
    
    elif call.data == 'shop_back':
        bot.edit_message_text(
            "🛒 Добро пожаловать в магазин! Выберите категорию:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=create_shop_keyboard()
        )
    
    elif call.data.startswith('donate_'):
        amount = int(call.data.split('_')[1])
        item = DONATE_PRICES[amount]
        
        donate_info = (
            f"💰 *Вы выбрали пакет:* {item}\n\n"
            f"💳 *Для оплаты переведите {amount}₽ на карту:*\n"
            f"`{BANK_CARD}`\n\n"
            f"📸 *После оплаты отправьте скриншот чека в этот чат*\n"
            f"⏳ *Обработка занимает до 24 часов*\n\n"
            f"👨‍💻 *Для вопросов:* @support_contact"
        )
        
        transaction_id = db.add_donate_transaction(user.id, amount, item)
        
        bot.edit_message_text(
            donate_info,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(
                    admin_id,
                    f"🛒 Новая заявка на донат!\n\n"
                    f"👤 Пользователь: {user.first_name} (@{user.username})\n"
                    f"🆔 ID: {user.id}\n"
                    f"💰 Сумма: {amount}₽\n"
                    f"🎁 Пакет: {item}\n"
                    f"📋 ID транзакции: {transaction_id}"
                )
            except:
                pass
    
    elif call.data.startswith('top_'):
        category = call.data.split('_')[1]
        top_users = db.get_top_users(category, 10)
        
        top_text = f"🏆 *Топ 10 игроков*\n\n"
        
        emojis = {
            'fish': '🐟',
            'money': '💰',
            'legendary': '👑',
            'level': '📈'
        }
        
        for i, user in enumerate(top_users, 1):
            if category == 'fish':
                value = user.get('total_fish', 0)
            elif category == 'money':
                value = user.get('money', 0)
            elif category == 'legendary':
                value = user.get('stats', {}).get('legendary', 0)
            elif category == 'level':
                value = user.get('level', 1)
            
            name = user.get('first_name', 'Неизвестно')[:15]
            top_text += f"{i}. {name}: {value} {emojis.get(category, '🏆')}\n"
        
        bot.edit_message_text(
            top_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
    
    elif call.data.startswith('users_'):
        # Пагинация списка пользователей
        action, page = call.data.split('_')[1], int(call.data.split('_')[2])
        users = db.get_all_users()
        total_pages = (len(users) + 9) // 10
        
        if action == 'next':
            page = min(page + 1, total_pages - 1)
        elif action == 'prev':
            page = max(page - 1, 0)
        
        start_idx = page * 10
        end_idx = min(start_idx + 10, len(users))
        
        markup = types.InlineKeyboardMarkup()
        btn_prev = types.InlineKeyboardButton("⬅️", callback_data=f"users_prev_{page}")
        btn_next = types.InlineKeyboardButton("➡️", callback_data=f"users_next_{page}")
        markup.add(btn_prev, btn_next)
        
        users_text = f"👥 *Список игроков ({start_idx+1}-{end_idx} из {len(users)}):*\n\n"
        for i, user in enumerate(users[start_idx:end_idx], start_idx + 1):
            users_text += f"{i}. {user.get('first_name', 'Неизвестно')} (@{user.get('username', 'нет')})\n"
            users_text += f"   🆔 ID: {user.get('id', 'N/A')}\n"
            users_text += f"   🎣 Уровень: {user.get('level', 1)}\n"
            users_text += f"   🐟 Рыбы: {user.get('total_fish', 0)}\n\n"
        
        bot.edit_message_text(
            users_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown',
            reply_markup=markup
        )

# ========== SCREENSHOT HANDLER ==========
@bot.message_handler(content_types=['photo'])
def handle_screenshot(message):
    user = message.from_user
    
    # Проверяем, есть ли незавершенные транзакции
    user_transactions = [t for t in db.donate_transactions 
                        if t['user_id'] == str(user.id) and not t['processed']]
    
    if user_transactions:
        # Берем последнюю транзакцию
        transaction = user_transactions[-1]
        
        # Сохраняем информацию о скриншоте
        transaction['screenshot'] = {
            'file_id': message.photo[-1].file_id,
            'date': datetime.now().isoformat()
        }
        
        # Уведомляем админов
        for admin_id in ADMIN_IDS:
            try:
                bot.send_photo(
                    admin_id,
                    message.photo[-1].file_id,
                    caption=f"📸 Чек от {user.first_name} (@{user.username})\n"
                           f"🆔 ID: {user.id}\n"
                           f"💰 Сумма: {transaction['amount']}₽\n"
                           f"🎁 Пакет: {transaction['item']}\n"
                           f"📋 ID транзакции: {transaction['id']}\n\n"
                           f"Для выдачи используйте команду:\n"
                           f"/issuedonate {transaction['id']}"
                )
            except:
                pass
        
        bot.reply_to(
            message,
            "✅ Скриншот чека получен! Администратор обработает ваш платеж в течение 24 часов."
        )
        
        db.save_data()

# ========== ADMIN DONATE COMMAND ==========
@bot.message_handler(commands=['issuedonate'])
def issue_donate_command(message):
    user = message.from_user
    if user.id not in ADMIN_IDS:
        return
    
    try:
        transaction_id = int(message.text.split()[1])
        
        # Находим транзакцию
        transaction = None
        for t in db.donate_transactions:
            if t['id'] == transaction_id:
                transaction = t
                break
        
        if not transaction:
            bot.reply_to(message, "❌ Транзакция не найдена")
            return
        
        if transaction['processed']:
            bot.reply_to(message, "❌ Транзакция уже обработана")
            return
        
        user_id = transaction['user_id']
        item = transaction['item']
        amount = transaction['amount']
        
        user_data = db.get_user_new(user_id)
        
        # Выдаем бонусы
        if "Пакет наживки" in item:
            for bait in ['red_oparysh', 'white_oparysh', 'motyl', 'earthworm', 'manure_worm', 'bread', 'corn', 'dough', 'worm_bundle']:
                user_data['baits'][bait] = user_data['baits'].get(bait, 0) + 10
        elif "Улучшение удачи" in item:
            if "+10%" in item:
                user_data['luck_boost'] = 10
            elif "+20%" in item:
                user_data['luck_boost'] = 20
        elif "Улучшение удочки" in item:
            user_data['unbreakable_rod'] = True
        elif "Спиннинг Pro" in item:
            if 'spinning_pro' not in user_data['rods']:
                user_data['rods'].append('spinning_pro')
            user_data['active_rod'] = 'spinning_pro'
            user_data['rod_durability']['spinning_pro'] = 300
        elif "Рыбоп" in item:
            if amount == 99:
                user_data['money'] += 1000
            elif amount == 199:
                user_data['money'] += 2500
            elif amount == 299:
                user_data['money'] += 5000
                user_data['unbreakable_rod'] = True
            elif amount == 499:
                user_data['money'] += 10000
                user_data['unbreakable_rod'] = True
                user_data['luck_boost'] = 30
                if 'spinning_pro' not in user_data['rods']:
                    user_data['rods'].append('spinning_pro')
                user_data['active_rod'] = 'spinning_pro'
        
        transaction['processed'] = True
        transaction['processed_by'] = user.id
        transaction['processed_at'] = datetime.now().isoformat()
        
        db.users[user_id] = user_data
        db.save_data()
        db.log_action(user.id, "обработал донат", f"Транзакция {transaction_id} для пользователя {user_id}")
        
        # Уведомляем пользователя
        try:
            bot.send_message(
                user_id,
                f"🎉 Ваш донат обработан!\n\n"
                f"💰 Пакет: {item}\n"
                f"✅ Бонусы успешно начислены!\n\n"
                f"Спасибо за поддержку проекта! 🎣"
            )
        except:
            pass
        
        bot.reply_to(message, f"✅ Донат успешно выдан пользователю {user_id}")
        
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {str(e)}")

# ========== ОБРАБОТКА ВСЕХ СООБЩЕНИЙ (СТАРЫЕ - БЕЗ ИЗМЕНЕНИЙ!) ==========
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_messages(message):
    delete_links_in_group(message)
    
    text = message.text
    if text in ['🎣 Начать рыбалку', '📊 Статистика', '🎒 Инвентарь', '❓ Помощь', 
                '🎣 Забросить удочку', '📋 Меню', '📍 Сменить локацию', '🏆 Топы',
                '📰 Новости', '🛒 Магазин', '💰 Донат', '🔙 Главное меню',
                '🎁 Выдать донат', '📊 Статистика игрока', '📜 Логи действий',
                '👥 Список игроков', '⚡ Выдать предупреждение', '🚫 Забанить',
                '✅ Разбанить', '📢 Отправить новость']:
        return
    if text and text.startswith('/'):
        return

@bot.message_handler(content_types=['photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle_media_messages(message):
    delete_links_in_group(message)

# ========== DAILY TASKS ==========
def check_daily_tasks():
    """Проверяет и выдает ежедневные задания"""
    current_hour = datetime.now().hour
    
    if current_hour == 8:  # В 8 утра
        for user_id in db.users.keys():
            user_data = db.get_user_new(user_id)
            today = datetime.now().strftime("%Y-%m-%d")
            
            if 'daily_tasks' not in user_data or today not in user_data['daily_tasks']:
                task_type = random.choice(['catch', 'money'])
                reward = random.randint(100, 500)
                
                if 'daily_tasks' not in user_data:
                    user_data['daily_tasks'] = {}
                
                user_data['daily_tasks'][today] = {
                    'type': task_type,
                    'progress': 0,
                    'target': 3 if task_type == 'catch' else 5,
                    'reward': reward,
                    'completed': False
                }
                
                db.users[user_id] = user_data
                
                try:
                    task_text = "🎯 *Новое ежедневное задание!*\n\n"
                    if task_type == 'catch':
                        task_text += "Поймайте 3 рыбы\n"
                    else:
                        task_text += "Заработайте 500 рыбопов\n"
                    task_text += f"Награда: {reward} рыбопов"
                    
                    bot.send_message(user_id, task_text, parse_mode='Markdown')
                except:
                    pass
        
        db.save_data()

# ========== NEWS BROADCAST ==========
def broadcast_news():
    """Рассылает новости всем пользователям"""
    unread_news = [n for n in db.news if not n.get('sent_to_all', False)]
    
    for news in unread_news:
        news_text = f"📢 *{news['title']}*\n\n{news['content']}"
        
        for user_id in db.users.keys():
            try:
                bot.send_message(user_id, news_text, parse_mode='Markdown')
            except:
                pass
        
        news['sent_to_all'] = True
    
    if unread_news:
        db.save_data()

# ========== WEBHOOK ROUTES ==========
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
    return "🎣 Complete Fishing Bot is running! Use /set_webhook to configure", 200

@app.route('/health')
def health():
    return "OK", 200

@app.route('/set_webhook')
def set_webhook():
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

# ========== RUN BOT ==========
if __name__ == '__main__':
    print("=" * 50)
    print("🎣 Complete Fishing Bot Webhook Edition")
    print(f"✅ Bot Token: {BOT_TOKEN[:10]}...")
    print(f"✅ Webhook URL: {WEBHOOK_URL if WEBHOOK_URL else 'Not set'}")
    print(f"✅ Admin IDs: {ADMIN_IDS}")
    print(f"✅ Users loaded: {len(db.users)}")
    print("=" * 50)
    
    # Запускаем keep-alive
    if RENDER_URL:
        keeper = KeepAliveService(RENDER_URL)
        keeper.start()
        print("✅ Keep-alive service started")
    
    # Запускаем фоновые задачи
    def background_tasks():
        while True:
            try:
                check_daily_tasks()
                broadcast_news()
            except Exception as e:
                print(f"Background task error: {e}")
            time.sleep(3600)  # Каждый час
    
    bg_thread = threading.Thread(target=background_tasks, daemon=True)
    bg_thread.start()
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Starting Flask on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
