#!/usr/bin/env python3
# bot_fish_advanced.py - Продвинутый бот для рыбалки
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
import string

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

# Настройки игры
FISHING_TIME = 30
WARNING_EXPIRE_TIME = 86400  # 24 часа
BAN_DURATION = 172800  # 2 дня

# Список администраторов
ADMIN_IDS = [8351629145, 7093049365, 5330661807]  # Добавлен третий админ как просили

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

# ========== НАЖИВКИ ==========
BAITS = {
    "red_oparysh": {
        "name": "🔴 Красный опарыш",
        "price": 5,  # в рыбопах
        "effectiveness": {"щука": 0.1, "окунь": 0.3, "плотва": 0.4, "лещ": 0.5, "карась": 0.6},
        "emoji": "🔴"
    },
    "white_oparysh": {
        "name": "⚪ Белый опарыш",
        "price": 3,
        "effectiveness": {"карась": 0.7, "плотва": 0.5, "лещ": 0.4, "окунь": 0.2, "густера": 0.3},
        "emoji": "⚪"
    },
    "motyl": {
        "name": "🟤 Мотыль",
        "price": 10,
        "effectiveness": {"лещ": 0.8, "плотва": 0.6, "окунь": 0.4, "карась": 0.5, "густера": 0.7},
        "emoji": "🟤"
    },
    "earthworm": {
        "name": "🟫 Дождевой червь",
        "price": 2,
        "effectiveness": {"сом": 0.6, "налим": 0.5, "язь": 0.4, "голавль": 0.3, "окунь": 0.2},
        "emoji": "🟫"
    },
    "manure_worm": {
        "name": "🟨 Навозный червь",
        "price": 4,
        "effectiveness": {"карась": 0.8, "плотва": 0.6, "лещ": 0.5, "линь": 0.4, "окунек": 0.3},
        "emoji": "🟨"
    },
    "simple_worm": {
        "name": "🐛 Обычный червь",
        "price": 0,  # бесплатный
        "effectiveness": {"плотва": 0.3, "окунь": 0.2, "карась": 0.4, "ерш": 0.5, "пескарь": 0.6},
        "emoji": "🐛"
    }
}

# ========== УДОЧКИ ==========
RODS = {
    "simple": {
        "name": "🎣 Простая удочка",
        "price": 0,
        "luck": 0.0,
        "durability": 50,
        "max_weight": 2.0,  # кг
        "category": "поплавочная",
        "break_chance": 0.1,
        "emoji": "🎣"
    },
    "float": {
        "name": "🎣 Поплавочная удочка",
        "price": 100,
        "luck": 0.05,
        "durability": 100,
        "max_weight": 3.0,
        "category": "поплавочная",
        "break_chance": 0.08,
        "emoji": "🎣"
    },
    "spinning": {
        "name": "🎣 Спиннинг обычный",
        "price": 500,
        "luck": 0.1,
        "durability": 150,
        "max_weight": 5.0,
        "category": "спиннинг",
        "break_chance": 0.06,
        "emoji": "🎣"
    },
    "spinning_pro": {
        "name": "🎣 Спиннинг Pro",
        "price": 2000,
        "luck": 0.3,
        "durability": 300,
        "max_weight": 10.0,
        "category": "спиннинг",
        "break_chance": 0.03,
        "emoji": "🎣"
    },
    "winter": {
        "name": "⛸️ Зимняя удочка",
        "price": 300,
        "luck": 0.0,
        "durability": 80,
        "max_weight": 1.5,
        "category": "зимняя",
        "break_chance": 0.12,
        "emoji": "⛸️"
    },
    "feeder": {
        "name": "🎣 Фидерная удочка",
        "price": 800,
        "luck": 0.15,
        "durability": 200,
        "max_weight": 6.0,
        "category": "донная",
        "break_chance": 0.05,
        "emoji": "🎣"
    },
    "carp": {
        "name": "🐟 Карповая удочка",
        "price": 1500,
        "luck": 0.2,
        "durability": 250,
        "max_weight": 15.0,
        "category": "карповая",
        "break_chance": 0.04,
        "emoji": "🐟"
    },
    "sea": {
        "name": "🌊 Морская удочка",
        "price": 3000,
        "luck": 0.25,
        "durability": 400,
        "max_weight": 25.0,
        "category": "морская",
        "break_chance": 0.02,
        "emoji": "🌊"
    },
    "telescopic": {
        "name": "🔭 Телескопическая удочка",
        "price": 400,
        "luck": 0.08,
        "durability": 120,
        "max_weight": 4.0,
        "category": "универсальная",
        "break_chance": 0.07,
        "emoji": "🔭"
    }
}

# ========== РЫБА (100 видов из России) ==========
FISHES = []
# Генерируем 100 видов рыб
fish_base = [
    # Пресноводные рыбы
    ("Щука обыкновенная", "хищная", 1.0, 15.0),
    ("Окунь речной", "хищная", 0.1, 2.0),
    ("Карась серебряный", "мирная", 0.2, 1.5),
    ("Карась золотой", "мирная", 0.3, 2.0),
    ("Лещ", "мирная", 0.5, 6.0),
    ("Плотва", "мирная", 0.1, 1.0),
    ("Густера", "мирная", 0.2, 1.2),
    ("Ёрш", "хищная", 0.05, 0.3),
    ("Налим", "хищная", 0.5, 18.0),
    ("Язь", "мирная", 0.3, 4.0),
    ("Голавль", "хищная", 0.2, 4.0),
    ("Жерех", "хищная", 0.5, 8.0),
    ("Сазан", "мирная", 1.0, 20.0),
    ("Карп", "мирная", 1.0, 25.0),
    ("Линь", "мирная", 0.3, 4.0),
    ("Пескарь", "мирная", 0.02, 0.15),
    ("Уклейка", "мирная", 0.01, 0.1),
    ("Быстрянка", "мирная", 0.01, 0.08),
    ("Голец", "мирная", 0.02, 0.1),
    ("Вьюн", "мирная", 0.05, 0.2),
    ("Сом", "хищная", 5.0, 100.0),
    ("Судак", "хищная", 0.8, 12.0),
    ("Берш", "хищная", 0.3, 3.0),
    ("Чоп", "хищная", 0.2, 2.0),
    ("Минога", "хищная", 0.1, 1.0),
    ("Хариус", "хищная", 0.2, 2.5),
    ("Таймень", "хищная", 3.0, 40.0),
    ("Ленок", "хищная", 0.5, 6.0),
    ("Форель ручьевая", "хищная", 0.2, 2.0),
    ("Голец арктический", "хищная", 0.5, 10.0),
    ("Сиг", "хищная", 0.3, 5.0),
    ("Чир", "хищная", 0.5, 8.0),
    ("Пелядь", "хищная", 0.3, 4.0),
    ("Омуль", "хищная", 0.4, 5.0),
    ("Муксун", "хищная", 0.5, 8.0),
    ("Нельма", "хищная", 1.0, 15.0),
    ("Ряпушка", "хищная", 0.05, 0.2),
    ("Корюшка", "хищная", 0.02, 0.15),
    ("Снеток", "хищная", 0.01, 0.08),
    ("Ротан", "хищная", 0.05, 0.5),
    ("Подкаменщик", "хищная", 0.02, 0.15),
    ("Бычок-кругляк", "хищная", 0.05, 0.3),
    ("Бычок-песочник", "хищная", 0.03, 0.2),
    ("Амур белый", "мирная", 1.0, 25.0),
    ("Толстолобик", "мирная", 2.0, 35.0),
    ("Змееголов", "хищная", 1.0, 8.0),
    ("Верхогляд", "хищная", 0.5, 10.0),
    ("Желтощёк", "хищная", 1.0, 15.0),
    ("Конь-губарь", "мирная", 0.3, 2.0),
    ("Подуст", "мирная", 0.2, 1.5),
    ("Елец", "мирная", 0.05, 0.3),
    ("Синец", "мирная", 0.2, 1.0),
    ("Белоглазка", "мирная", 0.2, 1.0),
    ("Краснопёрка", "мирная", 0.1, 1.0),
    ("Горчак", "мирная", 0.02, 0.08),
    ("Верховка", "мирная", 0.005, 0.03),
    ("Чехонь", "хищная", 0.2, 1.5),
    ("Атерина", "хищная", 0.02, 0.1),
    ("Игла-рыба", "хищная", 0.05, 0.3),
    ("Звездчатая камбала", "хищная", 0.2, 3.0),
    ("Речная камбала", "хищная", 0.3, 4.0),
    ("Палтус", "хищная", 5.0, 100.0),
    ("Треска", "хищная", 1.0, 25.0),
    ("Пикша", "хищная", 0.5, 15.0),
    ("Сайда", "хищная", 0.5, 10.0),
    ("Мерланг", "хищная", 0.3, 2.0),
    ("Мойва", "хищная", 0.02, 0.05),
    ("Сельдь атлантическая", "хищная", 0.2, 0.8),
    ("Сельдь тихоокеанская", "хищная", 0.2, 0.8),
    ("Килька", "хищная", 0.01, 0.03),
    ("Сардина", "хищная", 0.1, 0.3),
    ("Анчоус", "хищная", 0.02, 0.05),
    ("Ставрида", "хищная", 0.1, 1.0),
    ("Скумбрия", "хищная", 0.3, 2.0),
    ("Тунец", "хищная", 10.0, 200.0),
    ("Меч-рыба", "хищная", 50.0, 400.0),
    ("Марлин", "хищная", 40.0, 300.0),
    ("Королевская макрель", "хищная", 5.0, 40.0),
    ("Барракуда", "хищная", 3.0, 20.0),
    ("Рыба-меч", "хищная", 30.0, 250.0),
    ("Луфарь", "хищная", 1.0, 10.0),
    ("Горбыль", "хищная", 0.5, 8.0),
    ("Морской окунь", "хищная", 0.3, 5.0),
    ("Терпуг", "хищная", 0.5, 6.0),
    ("Зубан", "хищная", 0.8, 12.0),
    ("Каменный окунь", "хищная", 0.2, 3.0),
    ("Сарган", "хищная", 0.3, 1.5),
    ("Кефаль", "мирная", 0.3, 4.0),
    ("Пеламида", "хищная", 1.0, 15.0),
    ("Бонито", "хищная", 2.0, 20.0),
    ("Ваху", "хищная", 5.0, 40.0),
    ("Дорадо", "хищная", 1.0, 12.0),
    ("Сибас", "хищная", 1.0, 10.0),
    ("Камбала-ёрш", "хищная", 0.5, 7.0),
    ("Палтус черный", "хищная", 10.0, 100.0),
    ("Палтус синекорый", "хищная", 20.0, 200.0),
    ("Треска арктическая", "хищная", 2.0, 30.0),
    ("Сайка", "хищная", 0.1, 0.3),
    ("Морская щука", "хищная", 1.0, 15.0),
    ("Скорпена", "хищная", 0.3, 3.0),
    ("Морской чёрт", "хищная", 5.0, 40.0),
    ("Скат", "хищная", 3.0, 50.0),
    ("Акула катран", "хищная", 5.0, 15.0),
    ("Акула сельдевая", "хищная", 20.0, 100.0),
    ("Акула голубая", "хищная", 50.0, 200.0),
]

# Генерируем полный список рыб с весами и редкостями
for i, (name, fish_type, min_weight, max_weight) in enumerate(fish_base[:100]):
    # Определяем редкость на основе максимального веса
    if max_weight >= 50:
        rarity = "легендарная"
        probability = 2
    elif max_weight >= 10:
        rarity = "эпическая"
        probability = 10
    elif max_weight >= 5:
        rarity = "редкая"
        probability = 25
    elif max_weight >= 1:
        rarity = "необычная"
        probability = 40
    else:
        rarity = "обычная"
        probability = 23
    
    # Генерируем рандомный вес в граммах
    weight_range = (min_weight * 1000, max_weight * 1000)
    
    FISHES.append({
        "id": i + 1,
        "name": name,
        "type": fish_type,
        "rarity": rarity,
        "probability": probability,
        "weight_range": weight_range,
        "emoji": "🐟" if fish_type == "мирная" else "🦈",
        "price_per_kg": random.randint(50, 500)  # цена за кг в рыбопах
    })

# ========== DATABASE ==========
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
            with open('users_data_advanced.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.users = data.get('users', {})
                self.news = data.get('news', [])
                self.logs = data.get('logs', [])
                self.donate_transactions = data.get('donate_transactions', [])
            print(f"✅ Загружено {len(self.users)} пользователей, {len(self.news)} новостей")
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
    
    def save_data(self):
        """Сохраняем данные в файл"""
        try:
            data = {
                'users': self.users,
                'news': self.news,
                'logs': self.logs,
                'donate_transactions': self.donate_transactions
            }
            with open('users_data_advanced.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("💾 Данные сохранены")
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
        self.save_data()
    
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
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                'id': user_id,
                'username': None,
                'first_name': None,
                'fish_caught': [],
                'total_fish': 0,
                'last_fishing_time': None,
                'stats': {
                    'common': 0, 'unusual': 0, 'rare': 0, 
                    'epic': 0, 'legendary': 0, 'trash': 0
                },
                'baits': {
                    'simple_worm': 10,
                    'red_oparysh': 0,
                    'white_oparysh': 0,
                    'motyl': 0,
                    'earthworm': 0,
                    'manure_worm': 0
                },
                'rods': ['simple'],
                'active_rod': 'simple',
                'rod_durability': {'simple': 50},
                'location': 1,
                'money': 100,  # Рыбопы
                'level': 1,
                'exp': 0,
                'luck_boost': 0,
                'unbreakable_rod': False,
                'warnings': [],
                'banned_until': None,
                'admin_level': 0,
                'daily_tasks': {},
                'achievements': []
            }
        
        user = self.users[user_id]
        
        # Проверяем наличие стандартных червей (минимум 10)
        if user['baits']['simple_worm'] < 10:
            user['baits']['simple_worm'] = 10
        
        # Очистка старых предупреждений
        current_time = time.time()
        user['warnings'] = [w for w in user['warnings'] if current_time - w < WARNING_EXPIRE_TIME]
        
        return user
    
    def get_all_users(self):
        """Получаем список всех пользователей"""
        return list(self.users.values())
    
    def get_top_users(self, criteria='total_fish', limit=10):
        """Топ пользователей по критерию"""
        users_list = list(self.users.values())
        
        if criteria == 'total_fish':
            users_list.sort(key=lambda x: x['total_fish'], reverse=True)
        elif criteria == 'money':
            users_list.sort(key=lambda x: x['money'], reverse=True)
        elif criteria == 'legendary':
            users_list.sort(key=lambda x: x['stats']['legendary'], reverse=True)
        elif criteria == 'level':
            users_list.sort(key=lambda x: x['level'], reverse=True)
        
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
                user['money'] += task['reward']
                self.save_data()
                return task['reward']
        return 0

db = UserDatabase()

# ========== UTILITY FUNCTIONS ==========
def calculate_catch(user_data, location_id):
    """Расчет улова с учетом наживки, удочки и местности"""
    location = FISHING_LOCATIONS[location_id - 1]
    
    # Выбираем наживку
    available_baits = [bait for bait, count in user_data['baits'].items() if count > 0]
    if not available_baits:
        return None, None
    
    selected_bait = random.choice(available_baits)
    
    # Определяем вероятность поймать рыбу
    base_probability = 70  # 70% базовый шанс
    
    # Учет удачи удочки
    rod = RODS[user_data['active_rod']]
    rod_luck = rod['luck'] * 100
    
    # Учет буста удачи пользователя
    user_luck = user_data.get('luck_boost', 0)
    
    total_probability = min(base_probability + rod_luck + user_luck, 95)
    
    if random.randint(1, 100) > total_probability:
        return None, selected_bait
    
    # Выбираем рыбу из доступных в локации
    location_fish_names = location['fish_types']
    available_fishes = [f for f in FISHES if any(fish_name in f['name'].lower() for fish_name in location_fish_names)]
    
    if not available_fishes:
        available_fishes = FISHES
    
    # Учет эффективности наживки
    bait_info = BAITS[selected_bait]
    effectiveness = bait_info['effectiveness']
    
    # Создаем взвешенный список рыб
    weighted_fishes = []
    for fish in available_fishes:
        weight = fish['probability']
        
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
    min_w, max_w = selected_fish['weight_range']
    exact_weight = random.randint(int(min_w), int(max_w))
    
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

def create_main_keyboard():
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

# ========== COMMAND HANDLERS ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    # Обновляем информацию о пользователе
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
            f"🐛 Наживок: {sum(user_data['baits'].values())}\n"
            f"💰 Рыбопов: {user_data['money']}\n"
            f"🎣 Удочка: {RODS[user_data['active_rod']]['name']}\n"
            f"📍 Локация: {FISHING_LOCATIONS[user_data['location']-1]['name']}\n\n"
            f"Используй кнопки ниже для игры!"
        )
        
        bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_keyboard())

@bot.message_handler(commands=['fishing'])
def fishing_command_handler(message):
    user = message.from_user
    user_id = str(user.id)
    
    if db.is_banned(user_id):
        return
    
    if user_id in db.active_fishing:
        bot.send_message(message.chat.id, "⏳ Вы уже рыбачите! Подождите...")
        return
    
    user_data = db.get_user(user.id)
    
    # Проверяем наличие наживки
    if sum(user_data['baits'].values()) <= 0:
        bot.send_message(message.chat.id, "😔 У вас нет наживки! Купите в магазине.")
        return
    
    # Начинаем рыбалку
    msg = bot.send_message(message.chat.id,
                          f"🎣 *Началась рыбалка!*\n\n"
                          f"📍 Локация: {FISHING_LOCATIONS[user_data['location']-1]['name']}\n"
                          f"🎣 Удочка: {RODS[user_data['active_rod']]['name']}\n"
                          f"⏳ Рыбалка продлится {FISHING_TIME} секунд\n\n"
                          f"Ждите... рыба клюёт!",
                          reply_markup=types.ReplyKeyboardRemove())
    
    def fishing_timer():
        time.sleep(FISHING_TIME)
        
        if user_id in db.active_fishing:
            del db.active_fishing[user_id]
        
        # Вычисляем улов
        catch_result, bait_used = calculate_catch(user_data, user_data['location'])
        
        if catch_result is None:
            # Не удалось поймать
            user_data['baits'][bait_used] -= 1
            db.save_data()
            
            result_text = (
                f"😔 *Рыбалка завершена!*\n\n"
                f"Рыба не клюнула...\n"
                f"Использована наживка: {BAITS[bait_used]['name']}\n"
                f"Попробуйте ещё раз!"
            )
        elif catch_result.get('rod_broken'):
            # Удочка сломалась
            user_data['baits'][bait_used] -= 1
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
            bait_used = catch_result['bait']
            
            user_data['baits'][bait_used] -= 1
            
            # Добавляем рыбу в инвентарь
            catch_record = {
                'fish': fish['name'],
                'rarity': fish['rarity'],
                'weight': f"{weight}г",
                'weight_g': weight,
                'emoji': fish['emoji'],
                'bait': bait_used,
                'location': user_data['location'],
                'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'price': (weight / 1000) * fish['price_per_kg']
            }
            
            user_data['fish_caught'].append(catch_record)
            if len(user_data['fish_caught']) > 50:
                user_data['fish_caught'] = user_data['fish_caught'][-50:]
            
            user_data['total_fish'] += 1
            
            # Обновляем статистику
            if fish['rarity'] == "обычная":
                user_data['stats']['common'] += 1
            elif fish['rarity'] == "необычная":
                user_data['stats']['unusual'] += 1
            elif fish['rarity'] == "редкая":
                user_data['stats']['rare'] += 1
            elif fish['rarity'] == "эпическая":
                user_data['stats']['epic'] += 1
            elif fish['rarity'] == "легендарная":
                user_data['stats']['legendary'] += 1
            
            # Начисляем деньги
            money_earned = int(catch_record['price'])
            user_data['money'] += money_earned
            
            # Добавляем опыт
            exp_gained = 10 if fish['rarity'] == "обычная" else 50
            user_data['exp'] += exp_gained
            
            # Проверяем уровень
            exp_needed = user_data['level'] * 100
            if user_data['exp'] >= exp_needed:
                user_data['level'] += 1
                user_data['exp'] = 0
                user_data['money'] += 500  # Бонус за уровень
                level_up_msg = f"\n\n🎊 *Поздравляем! Вы достигли {user_data['level']} уровня!* +500 рыбопов"
            else:
                level_up_msg = ""
            
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
                f"🎣 *Наживка:* {BAITS[bait_used]['name']}\n"
                f"📈 *Опыт:* +{exp_gained}\n"
                f"{level_up_msg}"
            )
        
        try:
            bot.send_message(message.chat.id, result_text, reply_markup=create_main_keyboard())
        except Exception as e:
            print(f"Ошибка отправки: {e}")
    
    db.active_fishing[user_id] = threading.Thread(target=fishing_timer)
    db.active_fishing[user_id].daemon = True
    db.active_fishing[user_id].start()

# Другие команды...
@bot.message_handler(func=lambda msg: msg.text == '🎣 Начать рыбалку')
def fishing_button_handler(message):
    fishing_command_handler(message)

@bot.message_handler(func=lambda msg: msg.text == '📍 Сменить локацию')
def location_handler(message):
    bot.send_message(message.chat.id, "Выберите локацию для рыбалки:", reply_markup=create_location_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '🎒 Инвентарь')
def inventory_handler(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    # Наживки
    baits_text = "🐛 *Наживки:*\n"
    for bait_id, count in user_data['baits'].items():
        if count > 0:
            baits_text += f"{BAITS[bait_id]['emoji']} {BAITS[bait_id]['name']}: {count} шт.\n"
    
    # Удочки
    rods_text = "\n🎣 *Удочки:*\n"
    for rod_id in user_data['rods']:
        rod = RODS[rod_id]
        durability = user_data['rod_durability'].get(rod_id, 100)
        rods_text += f"{rod['emoji']} {rod['name']}"
        if rod_id == user_data['active_rod']:
            rods_text += " (активна)"
        rods_text += f"\n  Прочность: {durability}/100\n"
    
    # Последние уловы
    catches_text = "\n🐟 *Последние уловы:*\n"
    if user_data['fish_caught']:
        for i, catch in enumerate(reversed(user_data['fish_caught'][-5:]), 1):
            catches_text += f"{i}. {catch['emoji']} {catch['fish']} ({catch['weight']})\n"
    else:
        catches_text += "Пока пусто\n"
    
    total_text = baits_text + rods_text + catches_text
    bot.send_message(message.chat.id, total_text, reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '📊 Статистика')
def stats_handler(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    stats_text = (
        f"📊 *Статистика {user.first_name}*\n\n"
        f"🎣 Уровень: {user_data['level']}\n"
        f"📈 Опыт: {user_data['exp']}/{user_data['level'] * 100}\n"
        f"💰 Рыбопов: {user_data['money']}\n"
        f"🐟 Всего поймано: {user_data['total_fish']}\n\n"
        f"📊 *По редкостям:*\n"
        f"🐟 Обычных: {user_data['stats']['common']}\n"
        f"🐠 Необычных: {user_data['stats']['unusual']}\n"
        f"🌟 Редких: {user_data['stats']['rare']}\n"
        f"💫 Эпических: {user_data['stats']['epic']}\n"
        f"👑 Легендарных: {user_data['stats']['legendary']}\n\n"
        f"📍 Текущая локация: {FISHING_LOCATIONS[user_data['location']-1]['name']}\n"
        f"🎣 Активная удочка: {RODS[user_data['active_rod']]['name']}"
    )
    
    bot.send_message(message.chat.id, stats_text, reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '🏆 Топы')
def tops_handler(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🐟 По количеству рыбы', callback_data='top_fish')
    btn2 = types.InlineKeyboardButton('💰 По рыбопам', callback_data='top_money')
    btn3 = types.InlineKeyboardButton('👑 По легендарным', callback_data='top_legendary')
    btn4 = types.InlineKeyboardButton('📈 По уровню', callback_data='top_level')
    markup.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(message.chat.id, "Выберите категорию для топа:", reply_markup=markup)

@bot.message_handler(func=lambda msg: msg.text == '📰 Новости')
def news_handler(message):
    user = message.from_user
    unread_news = db.get_unread_news(user.id)
    
    if unread_news:
        for news in unread_news[-5:]:  # Последние 5 новостей
            news_text = f"📢 *{news['title']}*\n\n{news['content']}\n\n_{news['timestamp'][:10]}_"
            bot.send_message(message.chat.id, news_text, parse_mode='Markdown')
        
        db.mark_news_as_read(user.id)
    else:
        bot.send_message(message.chat.id, "📰 Нет новых новостей. Все актуальные новости вы уже прочитали!", reply_markup=create_main_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '🛒 Магазин')
def shop_handler(message):
    bot.send_message(message.chat.id, "🛒 Добро пожаловать в магазин! Выберите категорию:", reply_markup=create_shop_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '💰 Донат')
def donate_handler(message):
    donate_text = (
        "💰 *Поддержать проект*\n\n"
        "Ваша поддержка помогает развивать проект!\n"
        "За донат вы получаете различные бонусы.\n\n"
        "Выберите пакет:"
    )
    bot.send_message(message.chat.id, donate_text, reply_markup=create_donate_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '❓ Помощь')
def help_handler(message):
    help_text = (
        "🎣 *Помощь по игре \"Продвинутая рыбалка\"*\n\n"
        "📋 *Основные кнопки:*\n"
        "🎣 Начать рыбалку - начать ловлю рыбы\n"
        "📍 Сменить локацию - выбрать водоем\n"
        "🎒 Инвентарь - ваши наживки и удочки\n"
        "📊 Статистика - ваши достижения\n"
        "🏆 Топы - лучшие игроки\n"
        "📰 Новости - последние обновления\n"
        "🛒 Магазин - купить снасти\n"
        "💰 Донат - поддержать проект\n\n"
        "🎮 *Как играть:*\n"
        "1️⃣ Выберите локацию\n"
        "2️⃣ Купите наживку в магазине\n"
        "3️⃣ Начните рыбалку\n"
        "4️⃣ Разные наживки приманивают разную рыбу\n"
        "5️⃣ Удочки могут ломаться от тяжелой рыбы\n"
        "6️⃣ Продавайте рыбу за рыбопы\n"
        "7️⃣ Улучшайте снаряжение\n\n"
        "📞 *Поддержка:* @support_contact"
    )
    bot.send_message(message.chat.id, help_text, reply_markup=create_main_keyboard())

# ========== ADMIN HANDLERS ==========
@bot.message_handler(func=lambda msg: db.get_user(msg.from_user.id)['admin_level'] >= 1 and msg.text == '🎁 Выдать донат')
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
        
        user_data = db.get_user(user_id)
        if not user_data:
            bot.send_message(message.chat.id, "❌ Пользователь не найден")
            return
        
        item = DONATE_PRICES[amount]
        
        # Обрабатываем донат
        if "Пакет наживки" in item:
            for bait in ['red_oparysh', 'white_oparysh', 'motyl', 'earthworm', 'manure_worm']:
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

@bot.message_handler(func=lambda msg: db.get_user(msg.from_user.id)['admin_level'] >= 1 and msg.text == '📊 Статистика игрока')
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
        f"🆔 ID: {user_data.get('id')}\n"
        f"🎣 Уровень: {user_data.get('level', 1)}\n"
        f"💰 Рыбопов: {user_data.get('money', 0)}\n"
        f"🐟 Всего рыбы: {user_data.get('total_fish', 0)}\n"
        f"📍 Локация: {FISHING_LOCATIONS[user_data.get('location', 1)-1]['name']}\n"
        f"⚠️ Предупреждений: {len(user_data.get('warnings', []))}\n"
        f"🚫 Забанен: {'Да' if user_data.get('banned_until') else 'Нет'}"
    )
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

# ... (остальные админ-хендлеры для 5 уровня) ...

# ========== CALLBACK HANDLERS ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user = call.from_user
    user_data = db.get_user(user.id)
    
    if call.data.startswith('location_'):
        location_id = int(call.data.split('_')[1])
        user_data['location'] = location_id
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
        
        if user_data['money'] >= bait_info['price']:
            user_data['money'] -= bait_info['price']
            user_data['baits'][bait_id] = user_data['baits'].get(bait_id, 0) + 5  # 5 шт за покупку
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
                value = user['total_fish']
            elif category == 'money':
                value = user['money']
            elif category == 'legendary':
                value = user['stats']['legendary']
            elif category == 'level':
                value = user['level']
            
            name = user.get('first_name', 'Неизвестно')
            top_text += f"{i}. {name}: {value} {emojis.get(category, '🏆')}\n"
        
        bot.edit_message_text(
            top_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
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
        
        user_data = db.get_user(user_id)
        
        # Выдаем бонусы
        if "Пакет наживки" in item:
            for bait in ['red_oparysh', 'white_oparysh', 'motyl', 'earthworm', 'manure_worm']:
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
    return "🎣 Advanced Fishing Bot is running!", 200

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

# ========== DAILY TASKS ==========
def check_daily_tasks():
    """Проверяет и выдает ежедневные задания"""
    current_hour = datetime.now().hour
    
    if current_hour == 8:  # В 8 утра
        for user_id in db.users.keys():
            user_data = db.get_user(user_id)
            today = datetime.now().strftime("%Y-%m-%d")
            
            if 'daily_tasks' not in user_data or today not in user_data['daily_tasks']:
                task_type = random.choice(['catch', 'money'])
                reward = random.randint(100, 500)
                db.add_daily_task(user_id, task_type, reward)
                
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

# ========== NEWS BROADCAST ==========
def broadcast_news():
    """Рассылает новости всем пользователям"""
    unread_news = [n for n in db.news if not n.get('sent_to_all', False)]
    
    for news in unread_news:
        send_news_to_all(news)

# ========== RUN BOT ==========
if __name__ == '__main__':
    print("=" * 50)
    print("🎣 Advanced Fishing Bot Webhook Edition")
    print(f"✅ Bot Token: {BOT_TOKEN[:10]}...")
    print(f"✅ Webhook URL: {WEBHOOK_URL if WEBHOOK_URL else 'Not set'}")
    print(f"✅ Admin IDs: {ADMIN_IDS}")
    print("=" * 50)
    
    # Запускаем keep-alive
    if RENDER_URL:
        keeper = KeepAliveService(RENDER_URL)
        keeper.start()
        print("✅ Keep-alive service started")
    
    # Запускаем Flask
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Starting Flask on port {port}...")
    
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
    
    app.run(host='0.0.0.0', port=port, debug=False)
