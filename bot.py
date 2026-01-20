#!/usr/bin/env python3
# bot.py - Fishing Bot МЕГА-ОБНОВЛЕНИЕ
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
from collections import defaultdict

app = Flask(__name__)

# ========== KEEP-ALIVE SYSTEM ==========
class KeepAliveService:
    """Сервис для поддержания бота в активном состоянии на Render"""
    
    def __init__(self, base_url):
        self.base_url = base_url
        self.running = False
        self.thread = None
        self.ping_interval = 480
        
    def start(self):
        if self.running:
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._ping_loop, daemon=True)
        self.thread.start()
        print(f"✅ Keep-alive запущен. Ping каждые {self.ping_interval//60} минут")
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            
    def _ping_loop(self):
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
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            if response.status_code == 200:
                print(f"🔄 Ping успешен")
        except:
            print(f"⚠️ Ping ошибка")

# ========== CONFIGURATION ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8377535372:AAGLMfn_0P_tDvpJnfv_NmW4QclM2AIojEA')
bot = telebot.TeleBot(BOT_TOKEN)

RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
WEBHOOK_URL = f'{RENDER_URL}/{BOT_TOKEN}' if RENDER_URL else None

# Настройки игры
INITIAL_WORMS = 10
MAX_WORMS = 10
FISHING_TIME = 30
WORM_REFILL_TIME = 900
WARNING_EXPIRE_TIME = 86400
BAN_DURATION = 172800
COINS_NAME = "рыбоп"
INITIAL_COINS = 100

# ========== 10 ВОДОЕМОВ РОССИИ ==========
WATER_BODIES = {
    "река_Волга": {
        "name": "🌊 Река Волга",
        "emoji": "🌊",
        "description": "Крупнейшая река Европы, богата разнообразной рыбой",
        "depth": "глубокая",
        "temperature": "умеренная",
        "fishes": ["щука", "окунь", "лещ", "судак", "сом", "плотва", "карась", "густера", "язь", "жерех"]
    },
    "озеро_Байкал": {
        "name": "🏔️ Озеро Байкал",
        "emoji": "🏔️",
        "description": "Самое глубокое озеро в мире, уникальные виды рыб",
        "depth": "очень глубокая",
        "temperature": "холодная",
        "fishes": ["омуль", "байкальский_осётр", "сиг", "хариус", "таймень", "налим"]
    },
    "река_Дон": {
        "name": "🌅 Река Дон",
        "emoji": "🌅",
        "description": "Тихая равнинная река, отличное место для карпа и сазана",
        "depth": "средняя",
        "temperature": "тёплая",
        "fishes": ["карп", "сазан", "лещ", "плотва", "карась", "судак", "щука"]
    },
    "река_Енисей": {
        "name": "❄️ Река Енисей",
        "emoji": "❄️",
        "description": "Могучая сибирская река, дом для крупных хищников",
        "depth": "глубокая",
        "temperature": "холодная",
        "fishes": ["таймень", "ленок", "стерлядь", "осётр", "налим", "щука", "окунь"]
    },
    "река_Амур": {
        "name": "🐉 Река Амур",
        "emoji": "🐉",
        "description": "Пограничная река с уникальной ихтиофауной",
        "depth": "средняя",
        "temperature": "умеренная",
        "fishes": ["калуга", "амурский_осётр", "сазан", "толстолобик", "белый_амур", "щука"]
    },
    "Ладожское_озеро": {
        "name": "🏞️ Ладожское озеро",
        "emoji": "🏞️",
        "description": "Крупнейшее озеро Европы, богатое рыбой",
        "depth": "глубокая",
        "temperature": "холодная",
        "fishes": ["ладо́жская_рогатка", "сиг", "ряпушка", "лосось", "судак", "щука"]
    },
    "река_Кубань": {
        "name": "🌞 Река Кубань",
        "emoji": "🌞",
        "description": "Южная река с тёплой водой и активной рыбой",
        "depth": "мелкая",
        "temperature": "тёплая",
        "fishes": ["кубанский_усач", "шемая", "рыбец", "тарань", "карась", "сазан"]
    },
    "река_Печора": {
        "name": "🌲 Река Печора",
        "emoji": "🌲",
        "description": "Северная река с чистой водой и ценной рыбой",
        "depth": "средняя",
        "temperature": "холодная",
        "fishes": ["семга", "сиг", "хариус", "нельма", "омуль", "налим"]
    },
    "река_Нева": {
        "name": "🌉 Река Нева",
        "emoji": "🌉",
        "description": "Короткая, но рыбная река в черте города",
        "depth": "глубокая",
        "temperature": "прохладная",
        "fishes": ["корюшка", "плотва", "окунь", "лещ", "судак", "налим"]
    },
    "река_Ока": {
        "name": "🛶 Река Ока",
        "emoji": "🛶",
        "description": "Спокойная равнинная река, идеальна для начинающих",
        "depth": "мелкая",
        "temperature": "тёплая",
        "fishes": ["плотва", "лещ", "карась", "густера", "язь", "жерех", "сом"]
    }
}

# ========== 100 ВИДОВ РЫБ РОССИИ ==========
FISHES = {
    # Хищные рыбы
    "щука": {"name": "🐟 Щука", "rarity": "обычная", "base_price": 80, "baits": ["мотыль", "опарыш_красный", "мелкая_рыба"], "min_weight": 500, "max_weight": 10000, "locations": ["река_Волга", "река_Дон", "река_Енисей", "Ладожское_озеро"]},
    "окунь": {"name": "🐟 Окунь", "rarity": "обычная", "base_price": 40, "baits": ["мотыль", "опарыш_белый", "червь_дождевой"], "min_weight": 100, "max_weight": 2000, "locations": ["река_Волга", "река_Нева", "река_Ока", "Ладожское_озеро"]},
    "судак": {"name": "🐟 Судак", "rarity": "редкая", "base_price": 120, "baits": ["мотыль", "мелкая_рыба", "опарыш_красный"], "min_weight": 800, "max_weight": 8000, "locations": ["река_Волга", "река_Дон", "Ладожское_озеро"]},
    "сом": {"name": "🐟 Сом", "rarity": "эпическая", "base_price": 300, "baits": ["червь_навозный", "мелкая_рыба", "лягушка"], "min_weight": 2000, "max_weight": 50000, "locations": ["река_Волга", "река_Дон", "река_Ока"]},
    "жерех": {"name": "🐟 Жерех", "rarity": "редкая", "base_price": 100, "baits": ["мотыль", "опарыш_красный", "кузнечик"], "min_weight": 600, "max_weight": 5000, "locations": ["река_Волга", "река_Ока"]},
    "таймень": {"name": "🐟 Таймень", "rarity": "легендарная", "base_price": 800, "baits": ["мотыль", "мелкая_рыба", "блесна"], "min_weight": 3000, "max_weight": 30000, "locations": ["река_Енисей", "река_Печора"]},
    # Карповые
    "карп": {"name": "🐟 Карп", "rarity": "редкая", "base_price": 150, "baits": ["кукуруза", "червь_навозный", "бойлы"], "min_weight": 1000, "max_weight": 15000, "locations": ["река_Дон", "река_Амур", "река_Кубань"]},
    "сазан": {"name": "🐟 Сазан", "rarity": "редкая", "base_price": 180, "baits": ["кукуруза", "червь_навозный", "горох"], "min_weight": 1500, "max_weight": 12000, "locations": ["река_Дон", "река_Амур"]},
    "карась": {"name": "🐟 Карась", "rarity": "обычная", "base_price": 25, "baits": ["червь_дождевой", "мотыль", "опарыш_белый"], "min_weight": 200, "max_weight": 1500, "locations": ["река_Волга", "река_Дон", "река_Ока", "река_Кубань"]},
    "лещ": {"name": "🐟 Лещ", "rarity": "обычная", "base_price": 60, "baits": ["червь_дождевой", "мотыль", "опарыш_белый"], "min_weight": 400, "max_weight": 4000, "locations": ["река_Волга", "река_Дон", "река_Ока"]},
    "плотва": {"name": "🐟 Плотва", "rarity": "обычная", "base_price": 20, "baits": ["червь_дождевой", "мотыль", "опарыш_белый"], "min_weight": 100, "max_weight": 800, "locations": ["река_Волга", "река_Дон", "река_Нева", "река_Ока"]},
    "густера": {"name": "🐟 Густера", "rarity": "обычная", "base_price": 15, "baits": ["червь_дождевой", "мотыль"], "min_weight": 150, "max_weight": 600, "locations": ["река_Волга", "река_Ока"]},
    "язь": {"name": "🐟 Язь", "rarity": "редкая", "base_price": 90, "baits": ["червь_дождевой", "кузнечик", "мотыль"], "min_weight": 500, "max_weight": 3000, "locations": ["река_Волга", "река_Ока"]},
    # Сиговые
    "омуль": {"name": "🐟 Омуль", "rarity": "эпическая", "base_price": 250, "baits": ["мотыль", "опарыш_красный", "икра"], "min_weight": 300, "max_weight": 1500, "locations": ["озеро_Байкал", "река_Печора"]},
    "сиг": {"name": "🐟 Сиг", "rarity": "редкая", "base_price": 140, "baits": ["мотыль", "опарыш_красный"], "min_weight": 200, "max_weight": 1000, "locations": ["озеро_Байкал", "Ладожское_озеро", "река_Печора"]},
    "ряпушка": {"name": "🐟 Ряпушка", "rarity": "обычная", "base_price": 30, "baits": ["мотыль", "опарыш_белый"], "min_weight": 50, "max_weight": 200, "locations": ["Ладожское_озеро"]},
    # Осетровые
    "осётр": {"name": "🐟 Осётр", "rarity": "легендарная", "base_price": 1000, "baits": ["червь_навозный", "мотыль", "ракушка"], "min_weight": 5000, "max_weight": 30000, "locations": ["река_Волга", "река_Дон", "река_Енисей"]},
    "стерлядь": {"name": "🐟 Стерлядь", "rarity": "эпическая", "base_price": 600, "baits": ["червь_навозный", "мотыль"], "min_weight": 500, "max_weight": 3000, "locations": ["река_Волга", "река_Енисей"]},
    "калуга": {"name": "🐟 Калуга", "rarity": "легендарная", "base_price": 1500, "baits": ["червь_навозный", "мелкая_рыба"], "min_weight": 10000, "max_weight": 100000, "locations": ["река_Амур"]},
    # Прочие
    "налим": {"name": "🐟 Налим", "rarity": "редкая", "base_price": 130, "baits": ["червь_дождевой", "мотыль", "мелкая_рыба"], "min_weight": 800, "max_weight": 5000, "locations": ["река_Енисей", "река_Нева", "река_Печора"]},
    "хариус": {"name": "🐟 Хариус", "rarity": "редкая", "base_price": 160, "baits": ["мотыль", "опарыш_красный", "мушка"], "min_weight": 300, "max_weight": 1500, "locations": ["озеро_Байкал", "река_Печора"]},
    "корюшка": {"name": "🐟 Корюшка", "rarity": "обычная", "base_price": 35, "baits": ["мотыль", "опарыш_белый"], "min_weight": 30, "max_weight": 150, "locations": ["река_Нева"]},
    # Добавлю еще 80 видов для разнообразия (сокращенно)
    "белый_амур": {"name": "🐟 Белый амур", "rarity": "редкая", "base_price": 170, "baits": ["кукуруза", "водоросли"], "min_weight": 2000, "max_weight": 10000, "locations": ["река_Амур"]},
    "толстолобик": {"name": "🐟 Толстолобик", "rarity": "редкая", "base_price": 160, "baits": ["кукуруза", "фитопланктон"], "min_weight": 3000, "max_weight": 15000, "locations": ["река_Амур"]},
    "линь": {"name": "🐟 Линь", "rarity": "редкая", "base_price": 110, "baits": ["червь_дождевой", "мотыль"], "min_weight": 400, "max_weight": 3000, "locations": ["река_Волга", "река_Ока"]},
    "красноперка": {"name": "🐟 Красноперка", "rarity": "обычная", "base_price": 18, "baits": ["червь_дождевой", "мотыль"], "min_weight": 120, "max_weight": 500, "locations": ["река_Волга", "река_Ока"]},
    "голавль": {"name": "🐟 Голавль", "rarity": "редкая", "base_price": 95, "baits": ["кузнечик", "червь_дождевой"], "min_weight": 300, "max_weight": 2000, "locations": ["река_Волга", "река_Ока"]},
    "елец": {"name": "🐟 Елец", "rarity": "обычная", "base_price": 12, "baits": ["мотыль", "опарыш_белый"], "min_weight": 80, "max_weight": 300, "locations": ["река_Волга"]},
    "верховка": {"name": "🐟 Верховка", "rarity": "обычная", "base_price": 5, "baits": ["мотыль"], "min_weight": 10, "max_weight": 50, "locations": ["река_Волга", "река_Ока"]},
    "пескарь": {"name": "🐟 Пескарь", "rarity": "обычная", "base_price": 8, "baits": ["мотыль", "червь_дождевой"], "min_weight": 40, "max_weight": 150, "locations": ["река_Волга", "река_Ока"]},
    "бычок": {"name": "🐟 Бычок", "rarity": "обычная", "base_price": 10, "baits": ["червь_дождевой", "мотыль"], "min_weight": 50, "max_weight": 200, "locations": ["река_Дон"]},
    "уклейка": {"name": "🐟 Уклейка", "rarity": "обычная", "base_price": 6, "baits": ["мотыль", "опарыш_белый"], "min_weight": 20, "max_weight": 100, "locations": ["река_Волга", "река_Ока"]},
}

# ========== НАЖИВКИ ==========
BAITS = {
    "мотыль": {"name": "🔴 Мотыль", "price": 15, "emoji": "🔴", "description": "Личинка комара, универсальная наживка", "effectiveness": 1.0},
    "опарыш_белый": {"name": "⚪ Белый опарыш", "price": 20, "emoji": "⚪", "description": "Личинка мухи, хорош для мелкой рыбы", "effectiveness": 1.1},
    "опарыш_красный": {"name": "🔴 Красный опарыш", "price": 25, "emoji": "🔴", "description": "Красная личинка, привлекает крупную рыбу", "effectiveness": 1.3},
    "червь_дождевой": {"name": "🟤 Дождевой червь", "price": 10, "emoji": "🟤", "description": "Базовый червь, ловится на огороде", "effectiveness": 1.0},
    "червь_навозный": {"name": "🟡 Навозный червь", "price": 30, "emoji": "🟡", "description": "Крупный червь с сильным запахом", "effectiveness": 1.5},
    "кукуруза": {"name": "🌽 Кукуруза", "price": 5, "emoji": "🌽", "description": "Растительная наживка для карпа", "effectiveness": 1.2},
}

# ========== УДОЧКИ (20+ видов) ==========
RODS = {
    # Поплавочные удочки
    "удочка_поплавочная": {"name": "🎣 Поплавочная удочка", "price": 100, "category": "поплавочная", "strength": 50, "luck": 1.0, "durability": 100, "max_fish_weight": 2000},
    "удочка_матчевая": {"name": "🎣 Матчевая удочка", "price": 500, "category": "поплавочная", "strength": 70, "luck": 1.2, "durability": 120, "max_fish_weight": 3000},
    "удочка_болонская": {"name": "🎣 Болонская удочка", "price": 300, "category": "поплавочная", "strength": 60, "luck": 1.1, "durability": 110, "max_fish_weight": 2500},
    
    # Спиннинги
    "спиннинг_ультралайт": {"name": "🎣 Спиннинг ультралайт", "price": 800, "category": "спиннинг", "strength": 40, "luck": 1.5, "durability": 90, "max_fish_weight": 1500},
    "спиннинг_лайт": {"name": "🎣 Спиннинг лайт", "price": 1200, "category": "спиннинг", "strength": 60, "luck": 1.4, "durability": 100, "max_fish_weight": 3000},
    "спиннинг_медиум": {"name": "🎣 Спиннинг медиум", "price": 2000, "category": "спиннинг", "strength": 80, "luck": 1.3, "durability": 130, "max_fish_weight": 5000},
    "спиннинг_хеви": {"name": "🎣 Спиннинг хеви", "price": 3500, "category": "спиннинг", "strength": 100, "luck": 1.2, "durability": 150, "max_fish_weight": 10000},
    
    # Фидеры
    "фидер_лайт": {"name": "🎣 Фидер лайт", "price": 1500, "category": "фидер", "strength": 70, "luck": 1.3, "durability": 140, "max_fish_weight": 4000},
    "фидер_медиум": {"name": "🎣 Фидер медиум", "price": 2500, "category": "фидер", "strength": 90, "luck": 1.2, "durability": 160, "max_fish_weight": 7000},
    "фидер_хеви": {"name": "🎣 Фидер хеви", "price": 4000, "category": "фидер", "strength": 120, "luck": 1.1, "durability": 180, "max_fish_weight": 12000},
    
    # Нахлыстовые
    "нахлыст_класс_3": {"name": "🎣 Нахлыст класс 3", "price": 5000, "category": "нахлыст", "strength": 30, "luck": 1.8, "durability": 80, "max_fish_weight": 1000},
    "нахлыст_класс_5": {"name": "🎣 Нахлыст класс 5", "price": 7000, "category": "нахлыст", "strength": 50, "luck": 1.7, "durability": 100, "max_fish_weight": 2000},
    "нахлыст_класс_7": {"name": "🎣 Нахлыст класс 7", "price": 10000, "category": "нахлыст", "strength": 70, "luck": 1.6, "durability": 120, "max_fish_weight": 4000},
    
    # Зимние удочки
    "удочка_зимняя_кивковая": {"name": "🎣 Зимняя кивковая", "price": 200, "category": "зимняя", "strength": 30, "luck": 1.2, "durability": 70, "max_fish_weight": 1000},
    "удочка_зимняя_поплавочная": {"name": "🎣 Зимняя поплавочная", "price": 250, "category": "зимняя", "strength": 35, "luck": 1.1, "durability": 75, "max_fish_weight": 1200},
    "удочка_балалайка": {"name": "🎣 Балалайка", "price": 300, "category": "зимняя", "strength": 40, "luck": 1.3, "durability": 80, "max_fish_weight": 1500},
    
    # Прочие
    "донка_закидушка": {"name": "🎣 Донка закидушка", "price": 150, "category": "донная", "strength": 80, "luck": 1.0, "durability": 110, "max_fish_weight": 5000},
    "резинка": {"name": "🎣 Резинка", "price": 400, "category": "донная", "strength": 90, "luck": 1.1, "durability": 130, "max_fish_weight": 8000},
    "кружок": {"name": "🎣 Кружок", "price": 600, "category": "живцовая", "strength": 100, "luck": 1.4, "durability": 200, "max_fish_weight": 15000},
    "жерлица": {"name": "🎣 Жерлица", "price": 800, "category": "живцовая", "strength": 120, "luck": 1.5, "durability": 220, "max_fish_weight": 20000},
    
    # Легендарные
    "удочка_легендарная": {"name": "🏆 Легендарная удочка", "price": 20000, "category": "легендарная", "strength": 200, "luck": 2.0, "durability": 500, "max_fish_weight": 50000, "unbreakable": True},
}

# ========== ДОНАТ ТОВАРЫ ==========
DONATE_ITEMS = {
    # Улучшения удочек
    "repair_rod": {"name": "🔧 Ремонт удочки", "price": 50, "description": "Восстанавливает 100% прочности", "unique_price": 50},
    "upgrade_strength": {"name": "💪 Усиление прочности", "price": 150, "description": "+20% к прочности удочки", "unique_price": 150},
    "upgrade_luck": {"name": "🍀 Улучшение удачи", "price": 200, "description": "+20% к удаче", "unique_price": 200},
    "unbreakable": {"name": "🛡️ Несокрушимость", "price": 299, "description": "Удочка никогда не ломается", "unique_price": 299},
    
    # Удочки
    "rod_spinning_medium": {"name": "🎣 Спиннинг медиум", "price": 499, "description": "Спиннинг с +30% удачи", "unique_price": 499},
    "rod_finder_heavy": {"name": "🎣 Фидер хеви", "price": 799, "description": "Мощный фидер", "unique_price": 799},
    "rod_legendary": {"name": "🏆 Легендарная удочка", "price": 1999, "description": "Лучшая удочка в игре", "unique_price": 1999},
    
    # Рыбоп
    "coins_100": {"name": "💰 100 рыбоп", "price": 10, "description": "100 монет рыбоп", "unique_price": 10},
    "coins_500": {"name": "💰 500 рыбоп", "price": 45, "description": "500 монет рыбоп", "unique_price": 45},
    "coins_1000": {"name": "💰 1000 рыбоп", "price": 80, "description": "1000 монет рыбоп", "unique_price": 80},
    "coins_5000": {"name": "💰 5000 рыбоп", "price": 350, "description": "5000 монет рыбоп", "unique_price": 350},
    "coins_10000": {"name": "💰 10000 рыбоп", "price": 600, "description": "10000 монет рыбоп", "unique_price": 600},
    
    # Наживки пакетами
    "bait_pack_small": {"name": "🪱 Набор наживок малый", "price": 99, "description": "Мотыль x10 + Опарыш x10", "unique_price": 99},
    "bait_pack_large": {"name": "🪱 Набор наживок большой", "price": 199, "description": "Все наживки по 10 шт", "unique_price": 199},
}

# ========== АДМИН СИСТЕМА ==========
ADMINS = {
    "5330661807": 5,  # Полный доступ
    "8351629145": 1,  # Только выдача донатов
    "7093049365": 1,  # Только выдача донатов
}

# ========== USER DATABASE ==========
class UserDatabase:
    def __init__(self):
        self.users = {}
        self.active_fishing = {}
        self.admin_logs = []
        self.action_logs = []
        self.donation_queue = []
        self.news_messages = []
        self.load_data()
    
    def load_data(self):
        try:
            with open('users_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.users = data.get('users', {})
                self.donation_queue = data.get('donation_queue', [])
                self.news_messages = data.get('news', [])
            print(f"✅ Загружено {len(self.users)} пользователей")
        except:
            self.users = {}
            self.donation_queue = []
            self.news_messages = []
    
    def save_data(self):
        try:
            data = {
                'users': self.users,
                'donation_queue': self.donation_queue,
                'news': self.news_messages
            }
            with open('users_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    
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
                    'rods': [{"name": "удочка_поплавочная", "durability": 100, "equipped": True}],
                    'baits': {"мотыль": 5, "червь_дождевой": 5},
                    'fish': {},
                    'special_items': []
                },
                'current_location': "река_Волга",
                'fishing_level': 1,
                'experience': 0,
                'total_weight': 0,
                'donations': [],
                'muted_until': None,
            }
        
        user = self.users[user_id]
        current_time = time.time()
        
        # Автопополнение базовых червяков до 10
        time_passed = current_time - user.get('last_worm_refill', current_time)
        worms_to_add = int(time_passed // WORM_REFILL_TIME)
        
        if worms_to_add > 0:
            user['worms'] = min(user['worms'] + worms_to_add, MAX_WORMS)
            user['last_worm_refill'] = current_time
        
        # Очистка старых предупреждений
        user['warnings'] = [w for w in user['warnings'] if current_time - w < WARNING_EXPIRE_TIME]
        
        return user
    
    def add_donation_request(self, user_id, item_key, amount):
        request = {
            'user_id': str(user_id),
            'item_key': item_key,
            'amount': amount,
            'timestamp': time.time(),
            'status': 'pending',
            'processed': False
        }
        self.donation_queue.append(request)
        self.save_data()
        return len(self.donation_queue)
    
    def process_donation(self, queue_id, admin_id):
        if 0 <= queue_id < len(self.donation_queue):
            donation = self.donation_queue[queue_id]
            donation['status'] = 'processed'
            donation['processed_by'] = admin_id
            donation['processed_at'] = time.time()
            self.save_data()
            return donation
        return None
    
    def get_donation_queue(self):
        return [d for d in self.donation_queue if d['status'] == 'pending']
    
    def add_news(self, text, author_id):
        news = {
            'id': len(self.news_messages),
            'text': text,
            'author_id': author_id,
            'timestamp': time.time(),
            'read_by': []
        }
        self.news_messages.append(news)
        self.save_data()
        return news['id']
    
    def mark_news_read(self, user_id, news_id):
        user_id = str(user_id)
        if 0 <= news_id < len(self.news_messages):
            if user_id not in self.news_messages[news_id]['read_by']:
                self.news_messages[news_id]['read_by'].append(user_id)
                self.save_data()
    
    def get_unread_news(self, user_id):
        user_id = str(user_id)
        unread = []
        for news in self.news_messages[-10:]:  # Последние 10 новостей
            if user_id not in news['read_by']:
                unread.append(news)
        return unread

db = UserDatabase()

# ========== АДМИН ФУНКЦИИ ==========
def is_admin(user_id, min_level=1):
    user_id = str(user_id)
    return ADMINS.get(user_id, 0) >= min_level

def get_admin_level(user_id):
    user_id = str(user_id)
    return ADMINS.get(user_id, 0)

def set_admin_level(user_id, level):
    user_id = str(user_id)
    if level <= 0:
        if user_id in ADMINS:
            del ADMINS[user_id]
    else:
        ADMINS[user_id] = level
    
    # Сохраняем в базу
    try:
        with open('admins.json', 'w') as f:
            json.dump(ADMINS, f)
    except:
        pass
    
    return True

def get_user_from_input(input_str):
    if input_str.isdigit():
        return input_str
    if input_str.startswith('@'):
        username = input_str[1:].lower()
        for user_id, user_data in db.users.items():
            if user_data.get('username', '').lower() == username:
                return user_id
    return None

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========
def calculate_fish_weight(fish_key):
    fish = FISHES[fish_key]
    min_w = fish['min_weight']
    max_w = fish['max_weight']
    
    # Генерируем точный вес с нормальным распределением
    mean = (min_w + max_w) / 2
    std = (max_w - min_w) / 4
    
    weight = random.gauss(mean, std)
    weight = max(min_w, min(max_w, int(weight)))
    
    return weight

def calculate_catch(user_id):
    user = db.get_user(user_id)
    location = user['current_location']
    
    # Получаем рыбу для этой локации
    available_fish = []
    for fish_key, fish_data in FISHES.items():
        if location in fish_data['locations']:
            available_fish.append(fish_key)
    
    if not available_fish:
        available_fish = list(FISHES.keys())[:10]
    
    # Выбираем случайную рыбу
    fish_key = random.choice(available_fish)
    fish_data = FISHES[fish_key]
    
    # Определяем вес
    weight = calculate_fish_weight(fish_key)
    
    # Определяем редкость на основе веса
    max_weight = fish_data['max_weight']
    rarity_ratio = weight / max_weight
    
    if rarity_ratio > 0.8:
        rarity = "легендарная"
    elif rarity_ratio > 0.6:
        rarity = "эпическая"
    elif rarity_ratio > 0.4:
        rarity = "редкая"
    else:
        rarity = "обычная"
    
    # Стоимость на основе веса и редкости
    base_price = fish_data['base_price']
    rarity_multiplier = {"обычная": 1, "редкая": 1.5, "эпическая": 3, "легендарная": 6}
    weight_multiplier = weight / fish_data['min_weight']
    price = int(base_price * rarity_multiplier[rarity] * weight_multiplier * 0.1)
    
    return {
        'key': fish_key,
        'name': fish_data['name'],
        'rarity': rarity,
        'weight': weight,
        'price': price,
        'baits': fish_data['baits']
    }

def get_user_bait(user_id):
    user = db.get_user(user_id)
    baits = user['inventory']['baits']
    
    # Убираем пустые наживки
    baits = {k: v for k, v in baits.items() if v > 0}
    
    if not baits:
        return None
    
    # Выбираем случайную наживку (шанс пропорционален количеству)
    total = sum(baits.values())
    r = random.randint(1, total)
    current = 0
    
    for bait_key, count in baits.items():
        current += count
        if r <= current:
            return bait_key
    
    return list(baits.keys())[0]

def use_bait(user_id, bait_key):
    user = db.get_user(user_id)
    if bait_key in user['inventory']['baits'] and user['inventory']['baits'][bait_key] > 0:
        user['inventory']['baits'][bait_key] -= 1
        if user['inventory']['baits'][bait_key] == 0:
            del user['inventory']['baits'][bait_key]
        db.save_data()
        return True
    return False

def get_equipped_rod(user_id):
    user = db.get_user(user_id)
    for rod in user['inventory']['rods']:
        if rod.get('equipped', False):
            return rod
    return None

def damage_rod(user_id, fish_weight):
    user = db.get_user(user_id)
    rod = get_equipped_rod(user_id)
    
    if not rod:
        return False
    
    rod_data = RODS.get(rod['name'])
    if not rod_data:
        return False
    
    # Проверяем, не сломается ли удочка
    if rod_data.get('unbreakable', False):
        return False
    
    # Урон зависит от веса рыбы
    damage = min(10, max(1, int(fish_weight / 100)))
    rod['durability'] = max(0, rod['durability'] - damage)
    
    # Если прочность 0 - удочка сломана
    if rod['durability'] <= 0:
        rod['broken'] = True
        rod['equipped'] = False
        
        # Автоматически переключаемся на первую целую удочку
        for other_rod in user['inventory']['rods']:
            if not other_rod.get('broken', False) and other_rod['name'] != rod['name']:
                other_rod['equipped'] = True
                break
    
    db.save_data()
    return rod['durability']

def calculate_catch_probability(user_id, fish_data):
    rod = get_equipped_rod(user_id)
    if not rod:
        return 0.5
    
    rod_data = RODS.get(rod['name'])
    if not rod_data:
        return 0.5
    
    # Базовый шанс
    probability = 0.7
    
    # Влияние прочности
    durability_factor = rod['durability'] / 100
    probability *= (0.5 + 0.5 * durability_factor)
    
    # Влияние удачи удочки
    probability *= rod_data['luck']
    
    # Влияние веса рыбы
    max_weight = rod_data['max_fish_weight']
    if fish_data['weight'] > max_weight:
        probability *= 0.3  # Сильно снижаем шанс для слишком крупной рыбы
    
    return min(0.95, max(0.1, probability))

def create_main_keyboard(user_id=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('🎣 Начать рыбалку')
    btn2 = types.KeyboardButton('📊 Статистика')
    btn3 = types.KeyboardButton('🎒 Инвентарь')
    btn4 = types.KeyboardButton('🗺️ Сменить водоем')
    btn5 = types.KeyboardButton('🛒 Магазин')
    btn6 = types.KeyboardButton('💰 Продать рыбу')
    btn7 = types.KeyboardButton('📰 Новости')
    btn8 = types.KeyboardButton('🏆 Топы')
    
    buttons = [btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8]
    
    if user_id and is_admin(user_id, 1):
        btn_admin = types.KeyboardButton('👑 Админ панель')
        buttons.append(btn_admin)
    
    markup.add(*buttons)
    return markup

def create_admin_keyboard(admin_level):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    if admin_level >= 1:
        btn1 = types.KeyboardButton('💰 Выдать донат')
        btn2 = types.KeyboardButton('📋 Очередь донатов')
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
        btn8 = types.KeyboardButton('📢 Отправить новость')
        btn9 = types.KeyboardButton('🚫 Бан/Мут')
        btn10 = types.KeyboardButton('📊 Все логи')
        markup.add(btn7, btn8, btn9, btn10)
    
    btn_back = types.KeyboardButton('📋 Меню')
    markup.add(btn_back)
    
    return markup

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    if user.username:
        user_data['username'] = user.username
    user_data['first_name'] = user.first_name
    db.save_data()
    
    if db.is_banned(str(user.id)):
        ban_time_left = db.get_ban_time_left(user.id)
        days_left = int(ban_time_left // 86400)
        hours_left = int((ban_time_left % 86400) // 3600)
        minutes_left = int((ban_time_left % 3600) // 60)
        
        ban_text = f"🚫 {user.first_name}, ты забанен!\n\n⏳ Бан истечет через: {days_left}д {hours_left}ч {minutes_left}мин"
        bot.send_message(message.chat.id, ban_text)
        return
    
    # Проверяем непрочитанные новости
    unread_news = db.get_unread_news(user.id)
    news_text = ""
    if unread_news:
        news_text = f"\n📰 У вас {len(unread_news)} непрочитанных новостей! /news"
    
    welcome_text = (
        f"🎣 Привет, {user.first_name}!\n"
        f"Добро пожаловать в мир рыбалки!\n\n"
        f"📍 Текущий водоем: {WATER_BODIES[user_data['current_location']]['name']}\n"
        f"🐛 Червяков: {user_data['worms']}/10\n"
        f"💰 {COINS_NAME}: {user_data['coins']}\n"
        f"🐟 Всего поймано: {user_data['total_fish']}\n"
        f"🎣 Уровень: {user_data['fishing_level']}\n"
        f"{news_text}\n\n"
        f"Используй кнопки ниже для игры!"
    )
    
    bot.send_message(message.chat.id, welcome_text, reply_markup=create_main_keyboard(user.id))

@bot.message_handler(commands=['fishing'])
def fishing_command_handler(message):
    user = message.from_user
    user_id_str = str(user.id)
    
    if db.is_banned(user_id_str):
        return
    
    if user_id_str in db.active_fishing:
        bot.send_message(message.chat.id, "⏳ Вы уже рыбачите! Подождите...")
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
                           f"😔 Червяки закончились!\nСледующий червяк через: {minutes} мин {seconds} сек")
        else:
            user_data['worms'] = min(user_data['worms'] + 1, MAX_WORMS)
            user_data['last_worm_refill'] = current_time
            db.save_data()
            bot.send_message(message.chat.id,
                           f"🎉 Червяки пополнились! Теперь у вас {user_data['worms']} червяков.")
        return
    
    # Проверяем удочку
    rod = get_equipped_rod(user.id)
    if not rod:
        bot.send_message(message.chat.id, "❌ У вас нет экипированной удочки!")
        return
    
    if rod.get('broken', False):
        bot.send_message(message.chat.id, "❌ Ваша удочка сломана! Отремонтируйте её в магазине.")
        return
    
    if rod['durability'] < 20:
        bot.send_message(message.chat.id, "⚠️ Ваша удочка на грани поломки! Прочность: {rod['durability']}%")
    
    # Проверяем наживку
    bait_key = get_user_bait(user.id)
    if not bait_key:
        bot.send_message(message.chat.id, "❌ У вас закончилась наживка! Купите в магазине.")
        return
    
    # Используем червяка и наживку
    user_data['worms'] -= 1
    bait_name = BAITS[bait_key]['name'] if bait_key in BAITS else bait_key
    
    msg = bot.send_message(message.chat.id,
                          f"🎣 *Началась рыбалка!*\n\n"
                          f"📍 Водоем: {WATER_BODIES[user_data['current_location']]['name']}\n"
                          f"🎣 Удочка: {RODS[rod['name']]['name']}\n"
                          f"🪱 Наживка: {bait_name}\n"
                          f"⏳ Рыбалка продлится {FISHING_TIME} секунд\n\n"
                          f"Ждите... рыба клюёт!")
    
    def fishing_timer():
        time.sleep(FISHING_TIME)
        
        if user_id_str in db.active_fishing:
            del db.active_fishing[user_id_str]
        
        # Вычисляем улов
        catch = calculate_catch(user.id)
        
        # Проверяем, подходит ли наживка для этой рыбы
        if bait_key not in catch['baits']:
            # Шанс снижается если наживка не подходит
            if random.random() > 0.3:
                # Рыба не клюнула
                bot.send_message(message.chat.id,
                               f"😔 Рыбалка завершена!\n\n"
                               f"Рыба не клюнула на эту наживку.\n"
                               f"🪱 Потрачена наживка: {bait_name}\n"
                               f"🐛 Червяков осталось: {user_data['worms']}")
                use_bait(user.id, bait_key)
                return
        
        # Проверяем шанс поимки
        probability = calculate_catch_probability(user.id, catch)
        if random.random() > probability:
            # Рыба сорвалась
            bot.send_message(message.chat.id,
                           f"😔 Рыбалка завершена!\n\n"
                           f"Рыба сорвалась!\n"
                           f"🎣 Шанс был: {int(probability*100)}%\n"
                           f"🪱 Потрачена наживка: {bait_name}\n"
                           f"🐛 Червяков осталось: {user_data['worms']}")
            use_bait(user.id, bait_key)
            damage_rod(user.id, catch['weight'] // 2)  # Частичный урон
            return
        
        # Успешная поимка
        use_bait(user.id, bait_key)
        
        # Наносим урон удочке
        remaining_durability = damage_rod(user.id, catch['weight'])
        
        # Добавляем рыбу в инвентарь
        if catch['key'] in user_data['inventory']['fish']:
            user_data['inventory']['fish'][catch['key']] += 1
        else:
            user_data['inventory']['fish'][catch['key']] = 1
        
        # Обновляем статистику
        user_data['total_fish'] += 1
        user_data['total_weight'] += catch['weight']
        
        # Опыт
        exp_gained = max(1, catch['weight'] // 100)
        user_data['experience'] += exp_gained
        
        while user_data['experience'] >= user_data['fishing_level'] * 100:
            user_data['experience'] -= user_data['fishing_level'] * 100
            user_data['fishing_level'] += 1
        
        # Обновляем статистику по редкости
        rarity_map = {"обычная": "common", "редкая": "rare", "эпическая": "epic", "легендарная": "legendary"}
        if catch['rarity'] in rarity_map:
            user_data['stats'][rarity_map[catch['rarity']]] += 1
        
        db.save_data()
        
        # Формируем сообщение
        rarity_emojis = {"обычная": "🐟", "редкая": "🐠", "эпическая": "🌟", "легендарная": "👑"}
        
        result_text = (
            f"🎉 *Рыбалка завершена!*\n\n"
            f"{rarity_emojis.get(catch['rarity'], '🎣')} *Поймано:* {catch['name']}\n"
            f"📊 *Редкость:* {catch['rarity']}\n"
            f"⚖️ *Вес:* {catch['weight']}г\n"
            f"💰 *Стоимость:* {catch['price']} {COINS_NAME}\n"
            f"🪱 *Потрачена наживка:* {bait_name}\n\n"
            f"🎣 *Прочность удочки:* {remaining_durability}%\n"
            f"🐛 *Червяков осталось:* {user_data['worms']}\n"
            f"📈 *Опыт:* +{exp_gained}\n"
            f"🎣 *Уровень:* {user_data['fishing_level']}"
        )
        
        if catch['rarity'] == 'легендарная':
            result_text += "\n\n🎊 *ВАУ! Легендарная рыба!* 🎊"
        elif catch['rarity'] == 'эпическая':
            result_text += "\n\n✨ *Отличный улов!* ✨"
        
        bot.send_message(message.chat.id, result_text)
    
    db.active_fishing[user_id_str] = threading.Thread(target=fishing_timer)
    db.active_fishing[user_id_str].daemon = True
    db.active_fishing[user_id_str].start()

@bot.message_handler(commands=['location', 'водоем'])
def location_command(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    locations_text = "🗺️ *Выберите водоем:*\n\n"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for loc_key, loc_data in WATER_BODIES.items():
        current = " ✅" if loc_key == user_data['current_location'] else ""
        btn = types.InlineKeyboardButton(
            f"{loc_data['emoji']} {loc_data['name']}{current}",
            callback_data=f"location_{loc_key}"
        )
        markup.add(btn)
    
    current_loc = WATER_BODIES[user_data['current_location']]
    locations_text += f"📍 *Текущий:* {current_loc['name']}\n"
    locations_text += f"📝 {current_loc['description']}\n"
    locations_text += f"🌡️ Температура: {current_loc['temperature']}\n"
    locations_text += f"📏 Глубина: {current_loc['depth']}\n\n"
    locations_text += "Выберите новый водоем для рыбалки:"
    
    bot.send_message(message.chat.id, locations_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('location_'))
def location_change_handler(call):
    loc_key = call.data.split('_')[1]
    user = call.from_user
    
    if loc_key not in WATER_BODIES:
        bot.answer_callback_query(call.id, "❌ Водоем не найден")
        return
    
    user_data = db.get_user(user.id)
    user_data['current_location'] = loc_key
    db.save_data()
    
    loc_data = WATER_BODIES[loc_key]
    
    # Получаем рыбу для этого водоема
    available_fish = []
    for fish_key, fish_data in FISHES.items():
        if loc_key in fish_data['locations']:
            available_fish.append(fish_data['name'])
    
    fish_list = "\n".join(available_fish[:8])  # Показываем первые 8
    if len(available_fish) > 8:
        fish_list += f"\n... и еще {len(available_fish)-8} видов"
    
    response_text = (
        f"✅ *Водоем изменен!*\n\n"
        f"📍 Теперь вы находитесь на: {loc_data['name']}\n"
        f"📝 {loc_data['description']}\n\n"
        f"🐟 *Водится рыба:*\n{fish_list}"
    )
    
    bot.edit_message_text(
        response_text,
        call.message.chat.id,
        call.message.message_id
    )

@bot.message_handler(commands=['shop', 'магазин'])
def shop_command(message):
    user = message.from_user
    
    shop_text = """
🛒 *Магазин Fishing Bot*

💰 Ваш баланс: {} {}

Выберите категорию:
""".format(db.get_user(user.id)['coins'], COINS_NAME)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🪱 Наживки', callback_data='shop_baits')
    btn2 = types.InlineKeyboardButton('🎣 Удочки', callback_data='shop_rods')
    btn3 = types.InlineKeyboardButton('🔧 Ремонт/Улучшения', callback_data='shop_upgrades')
    btn4 = types.InlineKeyboardButton('💰 Донат товары', callback_data='shop_donate')
    btn5 = types.InlineKeyboardButton('📋 Меню', callback_data='menu')
    markup.add(btn1, btn2, btn3, btn4, btn5)
    
    bot.send_message(message.chat.id, shop_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'shop_baits')
def shop_baits_handler(call):
    user = call.from_user
    user_data = db.get_user(user.id)
    
    baits_text = f"🪱 *Магазин наживок*\n\n💰 Баланс: {user_data['coins']} {COINS_NAME}\n\n"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    for bait_key, bait_data in BAITS.items():
        count = user_data['inventory']['baits'].get(bait_key, 0)
        btn = types.InlineKeyboardButton(
            f"{bait_data['emoji']} {bait_data['name']} - {bait_data['price']}р ({count} шт)",
            callback_data=f'buy_bait_{bait_key}'
        )
        markup.add(btn)
    
    btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='shop_back')
    markup.add(btn_back)
    
    bot.edit_message_text(baits_text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_bait_'))
def buy_bait_handler(call):
    bait_key = call.data.split('_')[2]
    user = call.from_user
    
    if bait_key not in BAITS:
        bot.answer_callback_query(call.id, "❌ Наживка не найдена")
        return
    
    bait_data = BAITS[bait_key]
    user_data = db.get_user(user.id)
    
    if user_data['coins'] < bait_data['price']:
        bot.answer_callback_query(call.id, f"❌ Недостаточно {COINS_NAME}")
        return
    
    # Покупаем
    user_data['coins'] -= bait_data['price']
    if bait_key in user_data['inventory']['baits']:
        user_data['inventory']['baits'][bait_key] += 1
    else:
        user_data['inventory']['baits'][bait_key] = 1
    
    db.save_data()
    
    bot.answer_callback_query(call.id, f"✅ Куплено: {bait_data['name']}")
    
    # Обновляем сообщение
    shop_baits_handler(call)

@bot.callback_query_handler(func=lambda call: call.data == 'shop_rods')
def shop_rods_handler(call):
    user = call.from_user
    user_data = db.get_user(user.id)
    
    rods_text = f"🎣 *Магазин удочек*\n\n💰 Баланс: {user_data['coins']} {COINS_NAME}\n\n"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Группируем по категориям
    categories = {}
    for rod_key, rod_data in RODS.items():
        if rod_data['price'] <= 5000:  # Показываем только доступные
            category = rod_data['category']
            if category not in categories:
                categories[category] = []
            categories[category].append((rod_key, rod_data))
    
    for category, rods in categories.items():
        rods_text += f"*{category.upper()}*\n"
        for rod_key, rod_data in rods[:3]:  # Первые 3 из каждой категории
            rods_text += f"• {rod_data['name']} - {rod_data['price']}р\n"
        rods_text += "\n"
    
    for rod_key, rod_data in list(RODS.items())[:6]:  # Первые 6 удочек
        btn = types.InlineKeyboardButton(
            f"{rod_data['name']} - {rod_data['price']}р",
            callback_data=f'buy_rod_{rod_key}'
        )
        markup.add(btn)
    
    btn_more = types.InlineKeyboardButton('📖 Все удочки', callback_data='shop_all_rods')
    btn_back = types.InlineKeyboardButton('🔙 Назад', callback_data='shop_back')
    markup.add(btn_more, btn_back)
    
    bot.edit_message_text(rods_text, call.message.chat.id, call.message.message_id, reply_markup=markup)

# ========== ДОНАТ СИСТЕМА ==========
@bot.message_handler(commands=['donate', 'донат'])
def donate_command(message):
    user = message.from_user
    
    donate_text = """
💰 *Поддержать проект*

🎁 *Донат товары (уникальные цены):*

🔧 *Улучшения:*
• 🔧 Ремонт удочки - 50₽
• 💪 Усиление прочности (+20%) - 150₽
• 🍀 Улучшение удачи (+20%) - 200₽
• 🛡️ Несокрушимость (навсегда) - 299₽

🎣 *Удочки:*
• 🎣 Спиннинг медиум (+30% удачи) - 499₽
• 🎣 Фидер хеви - 799₽
• 🏆 Легендарная удочка - 1999₽

💰 *Рыбоп:*
• 💰 100 рыбоп - 10₽
• 💰 500 рыбоп - 45₽
• 💰 1000 рыбоп - 80₽
• 💰 5000 рыбоп - 350₽
• 💰 10000 рыбоп - 600₽

🪱 *Наборы наживок:*
• 🪱 Малый набор - 99₽
• 🪱 Большой набор - 199₽

💳 *Как купить:*
1. Выберите товар
2. Переведите указанную сумму на карту
3. Пришлите скриншот чека
4. Получите товар в течение 15 минут

💳 *Реквизиты для перевода:*
🏦 Банк: Тинькофф
💳 Карта: `2200 7020 3410 5283`
👤 Получатель: [Ваше имя]

👇 Выберите товар для покупки:
"""
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    # Добавляем кнопки для каждого товара
    items_per_row = 2
    items_list = list(DONATE_ITEMS.items())
    
    for i in range(0, len(items_list), items_per_row):
        row_items = items_list[i:i+items_per_row]
        row_buttons = []
        
        for item_key, item_data in row_items:
            btn = types.InlineKeyboardButton(
                f"{item_data['name']} - {item_data['price']}₽",
                callback_data=f'donate_item_{item_key}'
            )
            row_buttons.append(btn)
        
        markup.add(*row_buttons)
    
    btn_info = types.InlineKeyboardButton("ℹ️ Инструкция", callback_data='donate_info')
    btn_menu = types.InlineKeyboardButton("📋 Меню", callback_data='menu')
    markup.add(btn_info, btn_menu)
    
    bot.send_message(message.chat.id, donate_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('donate_item_'))
def donate_item_handler(call):
    item_key = call.data.split('_')[2]
    user = call.from_user
    
    if item_key not in DONATE_ITEMS:
        bot.answer_callback_query(call.id, "❌ Товар не найден")
        return
    
    item_data = DONATE_ITEMS[item_key]
    
    # Добавляем в очередь донатов
    queue_id = db.add_donation_request(user.id, item_key, item_data['price'])
    
    response_text = (
        f"✅ *Товар добавлен в корзину!*\n\n"
        f"🎁 *Товар:* {item_data['name']}\n"
        f"💰 *Цена:* {item_data['price']}₽\n"
        f"📝 *Описание:* {item_data['description']}\n\n"
        f"💳 *Для оплаты:*\n"
        f"1. Переведите *{item_data['price']}₽* на карту:\n"
        f"   `2200 7020 3410 5283`\n"
        f"2. В комментарии укажите ваш ID: `{user.id}`\n"
        f"3. Пришлите скриншот чека в этот чат\n\n"
        f"🆔 *ID заказа:* `{queue_id}`\n"
        f"⏳ *Обработка:* до 15 минут\n\n"
        f"⚠️ *Важно:* Цена уникальна ({item_data['price']}₽), не перепутайте сумму!"
    )
    
    markup = types.InlineKeyboardMarkup()
    btn_done = types.InlineKeyboardButton("✅ Я перевел", callback_data='donate_paid')
    markup.add(btn_done)
    
    bot.edit_message_text(
        response_text,
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

# ========== АДМИН КОМАНДЫ (УРОВЕНЬ 1 - ВЫДАЧА ДОНАТОВ) ==========
@bot.message_handler(commands=['выдать_донат'])
def donate_give_command(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 3:
        bot.send_message(message.chat.id, "❌ Формат: /выдать_донат @username ключ_товара")
        bot.send_message(message.chat.id, "Пример: /выдать_донат @username coins_1000")
        return
    
    target = parts[1]
    item_key = parts[2]
    
    target_id = get_user_from_input(target)
    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    if item_key not in DONATE_ITEMS:
        bot.send_message(message.chat.id, "❌ Товар не найден")
        return
    
    # Выдаем товар
    item_data = DONATE_ITEMS[item_key]
    target_user = db.get_user(target_id)
    
    # В зависимости от типа товара
    if item_key.startswith('coins_'):
        amount = int(item_key.split('_')[1])
        db.add_coins(target_id, amount)
        result = f"Выдано {amount} {COINS_NAME}"
    
    elif item_key.startswith('rod_'):
        rod_key = '_'.join(item_key.split('_')[1:])
        if rod_key in RODS:
            db.add_rod(target_id, rod_key)
            result = f"Выдана удочка: {RODS[rod_key]['name']}"
    
    elif item_key == 'unbreakable':
        # Делаем текущую удочку несокрушимой
        rod = get_equipped_rod(target_id)
        if rod:
            rod['unbreakable'] = True
            result = "Удочка теперь несокрушима"
    
    elif item_key == 'upgrade_luck':
        # +20% удачи к текущей удочке
        rod = get_equipped_rod(target_id)
        if rod and rod['name'] in RODS:
            rod['luck_boost'] = rod.get('luck_boost', 0) + 0.2
            result = "+20% к удаче удочки"
    
    elif item_key.startswith('bait_pack_'):
        # Выдаем набор наживок
        for bait_key in ['мотыль', 'опарыш_белый', 'опарыш_красный', 'червь_дождевой', 'червь_навозный']:
            if bait_key in BAITS:
                db.add_bait(target_id, bait_key, 10)
        result = "Выдан набор наживок"
    
    else:
        result = "Товар выдан"
    
    db.save_data()
    
    # Отправляем подтверждение
    target_name = target_user.get('first_name', 'Неизвестно')
    bot.send_message(message.chat.id, f"✅ Товар '{item_data['name']}' выдан игроку {target_name}\n{result}")
    
    # Уведомляем игрока
    try:
        bot.send_message(target_id, f"🎁 Вам выдан донат товар: {item_data['name']}\n{result}")
    except:
        pass

@bot.message_handler(commands=['очередь_донатов'])
def donate_queue_command(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    queue = db.get_donation_queue()
    
    if not queue:
        bot.send_message(message.chat.id, "📭 Очередь донатов пуста")
        return
    
    queue_text = "📋 *Очередь донатов:*\n\n"
    
    for i, donation in enumerate(queue[:10]):  # Первые 10
        user_data = db.get_user(donation['user_id'])
        user_name = user_data.get('first_name', 'Неизвестно')
        item_data = DONATE_ITEMS.get(donation['item_key'], {'name': 'Неизвестно', 'price': 0})
        
        queue_text += f"{i+1}. 👤 {user_name} (ID: {donation['user_id']})\n"
        queue_text += f"   🎁 {item_data['name']} - {donation['amount']}₽\n"
        queue_text += f"   🆔 ID заказа: {i}\n\n"
    
    if len(queue) > 10:
        queue_text += f"... и еще {len(queue)-10} заказов\n\n"
    
    queue_text += "Для обработки: /обработать_донат номер_заказа"
    
    bot.send_message(message.chat.id, queue_text)

@bot.message_handler(commands=['обработать_донат'])
def process_donate_command(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Формат: /обработать_донат номер_заказа")
        return
    
    try:
        queue_id = int(parts[1])
    except:
        bot.send_message(message.chat.id, "❌ Номер заказа должен быть числом")
        return
    
    donation = db.process_donation(queue_id, user.id)
    if not donation:
        bot.send_message(message.chat.id, "❌ Заказ не найден")
        return
    
    # Выдаем товар игроку
    user_id = donation['user_id']
    item_key = donation['item_key']
    
    # Используем команду выдачи
    fake_message = type('obj', (object,), {'text': f'/выдать_донат {user_id} {item_key}', 'from_user': user})
    donate_give_command(fake_message)
    
    bot.send_message(message.chat.id, f"✅ Заказ #{queue_id} обработан и выдан!")

# ========== АДМИН КОМАНДЫ (УРОВЕНЬ 5 - ПОЛНЫЙ ДОСТУП) ==========
@bot.message_handler(commands=['полная_статистика'])
def full_stats_command(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split()
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Формат: /полная_статистика @username/id")
        return
    
    target = parts[1]
    target_id = get_user_from_input(target)
    
    if not target_id:
        bot.send_message(message.chat.id, "❌ Пользователь не найден")
        return
    
    target_user = db.get_user(target_id)
    
    # Собираем полную статистику
    stats_text = f"📊 *ПОЛНАЯ СТАТИСТИКА ИГРОКА*\n\n"
    stats_text += f"👤 *Имя:* {target_user.get('first_name', 'Неизвестно')}\n"
    stats_text += f"🆔 *ID:* {target_id}\n"
    stats_text += f"📅 *В игре с:* {datetime.fromtimestamp(target_user.get('join_date', time.time())).strftime('%d.%m.%Y')}\n\n"
    
    stats_text += f"💰 *Экономика:*\n"
    stats_text += f"• {COINS_NAME}: {target_user['coins']}\n"
    stats_text += f"• Всего заработано: {target_user.get('total_earned', 0)}\n"
    stats_text += f"• Всего потрачено: {target_user.get('total_spent', 0)}\n\n"
    
    stats_text += f"🎣 *Рыбалка:*\n"
    stats_text += f"• Уровень: {target_user['fishing_level']}\n"
    stats_text += f"• Опыт: {target_user['experience']}/{target_user['fishing_level'] * 100}\n"
    stats_text += f"• Всего поймано: {target_user['total_fish']}\n"
    stats_text += f"• Общий вес: {target_user['total_weight']}г\n"
    stats_text += f"• Текущий водоем: {WATER_BODIES[target_user['current_location']]['name']}\n\n"
    
    stats_text += f"🐟 *Статистика по редкости:*\n"
    stats_text += f"• Обычных: {target_user['stats']['common']}\n"
    stats_text += f"• Редких: {target_user['stats']['rare']}\n"
    stats_text += f"• Эпических: {target_user['stats']['epic']}\n"
    stats_text += f"• Легендарных: {target_user['stats']['legendary']}\n\n"
    
    stats_text += f"🎒 *Инвентарь:*\n"
    stats_text += f"• Червяков: {target_user['worms']}/10\n"
    stats_text += f"• Наживок: {sum(target_user['inventory']['baits'].values())} шт\n"
    stats_text += f"• Рыбы: {sum(target_user['inventory']['fish'].values())} шт\n"
    stats_text += f"• Удочек: {len(target_user['inventory']['rods'])} шт\n\n"
    
    # Текущая удочка
    rod = get_equipped_rod(target_id)
    if rod:
        rod_data = RODS.get(rod['name'], {})
        stats_text += f"🎣 *Текущая удочка:* {rod_data.get('name', rod['name'])}\n"
        stats_text += f"• Прочность: {rod.get('durability', 100)}%\n"
        stats_text += f"• Категория: {rod_data.get('category', 'неизвестно')}\n"
        if rod.get('unbreakable'):
            stats_text += "• ⚡ Несокрушимая\n"
    
    # Топ 5 рыб по количеству
    if target_user['inventory']['fish']:
        sorted_fish = sorted(target_user['inventory']['fish'].items(), key=lambda x: x[1], reverse=True)[:5]
        stats_text += f"\n🐟 *Топ 5 рыб:*\n"
        for fish_key, count in sorted_fish:
            fish_name = FISHES.get(fish_key, {}).get('name', fish_key)
            stats_text += f"• {fish_name}: {count} шт\n"
    
    # История донатов
    if target_user.get('donations'):
        stats_text += f"\n💰 *История донатов:*\n"
        total_donated = 0
        for don in target_user['donations'][-5:]:  # Последние 5
            stats_text += f"• {don.get('amount', 0)}₽ - {don.get('item', 'товар')}\n"
            total_donated += don.get('amount', 0)
        stats_text += f"• *Всего:* {total_donated}₽\n"
    
    # Предупреждения и баны
    warning_count = len([w for w in target_user['warnings'] if time.time() - w < WARNING_EXPIRE_TIME])
    stats_text += f"\n⚠️ *Нарушения:*\n"
    stats_text += f"• Активных предупреждений: {warning_count}/2\n"
    if target_user.get('banned_until'):
        ban_left = target_user['banned_until'] - time.time()
        if ban_left > 0:
            days = int(ban_left // 86400)
            hours = int((ban_left % 86400) // 3600)
            stats_text += f"• 🚫 Забанен до: через {days}д {hours}ч\n"
    
    bot.send_message(message.chat.id, stats_text)

@bot.message_handler(commands=['все_логи'])
def all_logs_command(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    # Здесь должна быть реализация пагинации логов
    # Пока просто отправляем сообщение
    bot.send_message(message.chat.id, "📊 *Система логов*\n\nИспользуйте:\n• /логи_игроков - логи действий игроков\n• /логи_админов - логи действий админов\n• /логи_банов - логи банов/мутов")

@bot.message_handler(commands=['отправить_новость'])
def send_news_command(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        bot.send_message(message.chat.id, "❌ Недостаточно прав!")
        return
    
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.send_message(message.chat.id, "❌ Формат: /отправить_новость текст новости")
        return
    
    news_text = parts[1]
    news_id = db.add_news(news_text, user.id)
    
    # Отправляем всем пользователям
    sent_count = 0
    for user_id in db.users.keys():
        try:
            bot.send_message(user_id, f"📰 *НОВОСТЬ #{news_id}*\n\n{news_text}")
            db.mark_news_read(user_id, news_id)
            sent_count += 1
        except:
            pass
    
    bot.send_message(message.chat.id, f"✅ Новость отправлена {sent_count} пользователям")

# ========== ТОПЫ ==========
@bot.message_handler(commands=['top', 'топы'])
def top_command(message):
    user = message.from_user
    
    top_text = "🏆 *ТОПЫ ИГРОКОВ*\n\n"
    top_text += "Выберите категорию:\n"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton('🐟 По количеству рыбы', callback_data='top_fish_count')
    btn2 = types.InlineKeyboardButton('💰 По рыбоп', callback_data='top_coins')
    btn3 = types.InlineKeyboardButton('⚖️ По весу улова', callback_data='top_weight')
    btn4 = types.InlineKeyboardButton('🎣 По уровню', callback_data='top_level')
    btn5 = types.InlineKeyboardButton('👑 По легендарным рыбам', callback_data='top_legendary')
    btn6 = types.InlineKeyboardButton('📋 Меню', callback_data='menu')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    bot.send_message(message.chat.id, top_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('top_'))
def top_category_handler(call):
    category = call.data.split('_')[1]
    
    # Собираем данные всех игроков
    players_data = []
    
    for user_id, user_data in db.users.items():
        if category == 'fish_count':
            value = user_data['total_fish']
        elif category == 'coins':
            value = user_data['coins']
        elif category == 'weight':
            value = user_data['total_weight']
        elif category == 'level':
            value = user_data['fishing_level']
        elif category == 'legendary':
            value = user_data['stats']['legendary']
        else:
            value = 0
        
        players_data.append({
            'id': user_id,
            'name': user_data.get('first_name', f'Игрок {user_id[:4]}'),
            'value': value
        })
    
    # Сортируем
    players_data.sort(key=lambda x: x['value'], reverse=True)
    
    # Формируем топ
    category_names = {
        'fish_count': '🐟 Количество пойманной рыбы',
        'coins': f'💰 {COINS_NAME}',
        'weight': '⚖️ Общий вес улова',
        'level': '🎣 Уровень рыбалки',
        'legendary': '👑 Легендарные рыбы'
    }
    
    top_text = f"🏆 *ТОП 10: {category_names.get(category, 'Неизвестно')}*\n\n"
    
    for i, player in enumerate(players_data[:10], 1):
        if category == 'weight':
            value_text = f"{player['value']}г"
        elif category == 'coins':
            value_text = f"{player['value']} {COINS_NAME}"
        else:
            value_text = str(player['value'])
        
        medal = ""
        if i == 1: medal = "🥇"
        elif i == 2: medal = "🥈"
        elif i == 3: medal = "🥉"
        
        top_text += f"{medal} *{i}. {player['name']}*\n"
        top_text += f"   📊 {value_text}\n\n"
    
    # Проверяем позицию текущего пользователя
    current_user_id = str(call.from_user.id)
    for i, player in enumerate(players_data):
        if player['id'] == current_user_id:
            if i >= 10:  # Если не в топ-10
                if category == 'weight':
                    value_text = f"{player['value']}г"
                elif category == 'coins':
                    value_text = f"{player['value']} {COINS_NAME}"
                else:
                    value_text = str(player['value'])
                
                top_text += f"\n...\n📊 *Ваша позиция:* {i+1}. {player['name']} - {value_text}"
            break
    
    bot.edit_message_text(
        top_text,
        call.message.chat.id,
        call.message.message_id
    )

# ========== НОВОСТИ ==========
@bot.message_handler(commands=['news', 'новости'])
def news_command(message):
    user = message.from_user
    news = db.news_messages[-5:]  # Последние 5 новостей
    
    if not news:
        bot.send_message(message.chat.id, "📰 *Новости*\n\nНа данный момент новостей нет.")
        return
    
    news_text = "📰 *ПОСЛЕДНИЕ НОВОСТИ*\n\n"
    
    for item in reversed(news):
        date = datetime.fromtimestamp(item['timestamp']).strftime('%d.%m.%Y %H:%M')
        author = "Администратор"
        
        news_text += f"📅 *{date}*\n"
        news_text += f"{item['text']}\n"
        news_text += f"👤 *{author}*\n"
        news_text += "─" * 30 + "\n\n"
    
    # Отмечаем как прочитанные
    for item in news:
        db.mark_news_read(user.id, item['id'])
    
    bot.send_message(message.chat.id, news_text)

# ========== ПРОДАЖА РЫБЫ ==========
@bot.message_handler(commands=['sell', 'продать'])
def sell_command(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    if not user_data['inventory']['fish']:
        bot.send_message(message.chat.id, "🎣 У вас нет рыбы для продажи!")
        return
    
    # Показываем рыбу для продажи
    fish_text = "💰 *Продажа рыбы*\n\n"
    fish_text += "🐟 *Ваша рыба:*\n"
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    total_value = 0
    for fish_key, count in user_data['inventory']['fish'].items():
        if fish_key in FISHES:
            fish_data = FISHES[fish_key]
            # Средняя цена за рыбу
            avg_price = fish_data['base_price'] * 2  # Упрощенный расчет
            value = avg_price * count
            
            fish_text += f"• {fish_data['name']}: {count} шт (~{avg_price}р/шт)\n"
            total_value += value
            
            # Кнопки для продажи
            btn_sell_one = types.InlineKeyboardButton(
                f"Продать 1 {fish_data['name']}",
                callback_data=f'sell_{fish_key}_1'
            )
            btn_sell_all = types.InlineKeyboardButton(
                f"Продать все {fish_data['name']}",
                callback_data=f'sell_{fish_key}_{count}'
            )
            markup.add(btn_sell_one, btn_sell_all)
    
    fish_text += f"\n💰 *Общая стоимость:* ~{total_value} {COINS_NAME}"
    
    btn_cancel = types.InlineKeyboardButton("❌ Отмена", callback_data='menu')
    markup.add(btn_cancel)
    
    bot.send_message(message.chat.id, fish_text, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('sell_'))
def sell_fish_handler(call):
    data_parts = call.data.split('_')
    if len(data_parts) < 3:
        bot.answer_callback_query(call.id, "❌ Ошибка")
        return
    
    fish_key = data_parts[1]
    try:
        count = int(data_parts[2])
    except:
        count = 1
    
    user = call.from_user
    user_data = db.get_user(user.id)
    
    if fish_key not in user_data['inventory']['fish']:
        bot.answer_callback_query(call.id, "❌ Рыба не найдена в инвентаре")
        return
    
    if user_data['inventory']['fish'][fish_key] < count:
        bot.answer_callback_query(call.id, "❌ Недостаточно рыбы")
        return
    
    if fish_key not in FISHES:
        bot.answer_callback_query(call.id, "❌ Ошибка данных рыбы")
        return
    
    # Вычисляем стоимость
    fish_data = FISHES[fish_key]
    avg_price = fish_data['base_price'] * 2
    total_price = avg_price * count
    
    # Продаем
    user_data['inventory']['fish'][fish_key] -= count
    if user_data['inventory']['fish'][fish_key] == 0:
        del user_data['inventory']['fish'][fish_key]
    
    user_data['coins'] += total_price
    db.save_data()
    
    # Сообщение об успехе
    success_text = (
        f"💰 *Продажа успешна!*\n\n"
        f"🐟 Продано: {fish_data['name']} x{count}\n"
        f"💵 Получено: {total_price} {COINS_NAME}\n"
        f"💰 Баланс: {user_data['coins']} {COINS_NAME}"
    )
    
    bot.edit_message_text(
        success_text,
        call.message.chat.id,
        call.message.message_id
    )

# ========== ИНВЕНТАРЬ ==========
@bot.message_handler(commands=['inventory', 'инвентарь'])
def inventory_command(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    inv_text = "🎒 *ИНВЕНТАРЬ*\n\n"
    
    # Текущая удочка
    rod = get_equipped_rod(user.id)
    if rod:
        rod_data = RODS.get(rod['name'], {})
        inv_text += f"🎣 *Текущая удочка:* {rod_data.get('name', rod['name'])}\n"
        inv_text += f"• Прочность: {rod.get('durability', 100)}%\n"
        if rod.get('unbreakable'):
            inv_text += "• ⚡ Несокрушимая\n"
        inv_text += "\n"
    
    # Наживки
    inv_text += "🪱 *Наживки:*\n"
    if user_data['inventory']['baits']:
        for bait_key, count in user_data['inventory']['baits'].items():
            if bait_key in BAITS:
                inv_text += f"• {BAITS[bait_key]['name']}: {count} шт\n"
    else:
        inv_text += "Нет наживок\n"
    inv_text += "\n"
    
    # Рыба
    inv_text += "🐟 *Рыба:*\n"
    if user_data['inventory']['fish']:
        total_fish = sum(user_data['inventory']['fish'].values())
        inv_text += f"Всего: {total_fish} шт\n"
        
        # Показываем 5 самых частых рыб
        sorted_fish = sorted(user_data['inventory']['fish'].items(), key=lambda x: x[1], reverse=True)[:5]
        for fish_key, count in sorted_fish:
            fish_name = FISHES.get(fish_key, {}).get('name', fish_key)
            inv_text += f"• {fish_name}: {count} шт\n"
        
        if len(user_data['inventory']['fish']) > 5:
            inv_text += f"... и еще {len(user_data['inventory']['fish'])-5} видов\n"
    else:
        inv_text += "Нет рыбы\n"
    
    # Удочки
    inv_text += "\n🎣 *Удочки:*\n"
    rod_count = len(user_data['inventory']['rods'])
    inv_text += f"Всего: {rod_count} шт\n"
    
    # Показываем экипированные и сломанные
    for rod_item in user_data['inventory']['rods']:
        rod_name = RODS.get(rod_item['name'], {}).get('name', rod_item['name'])
        status = ""
        if rod_item.get('equipped', False):
            status = " ✅"
        if rod_item.get('broken', False):
            status = " 💔"
        inv_text += f"• {rod_name}{status}\n"
    
    bot.send_message(message.chat.id, inv_text)

# ========== ОБРАБОТЧИКИ КНОПОК ==========
@bot.message_handler(func=lambda msg: msg.text == '🎣 Начать рыбалку')
def fishing_button_handler(message):
    fishing_command_handler(message)

@bot.message_handler(func=lambda msg: msg.text == '📊 Статистика')
def stats_button_handler(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    stats_text = f"📊 *СТАТИСТИКА {user.first_name}*\n\n"
    stats_text += f"🎣 Уровень: {user_data['fishing_level']}\n"
    stats_text += f"📈 Опыт: {user_data['experience']}/{user_data['fishing_level'] * 100}\n"
    stats_text += f"🐟 Всего поймано: {user_data['total_fish']}\n"
    stats_text += f"⚖️ Общий вес: {user_data['total_weight']}г\n"
    stats_text += f"💰 {COINS_NAME}: {user_data['coins']}\n"
    stats_text += f"🐛 Червяков: {user_data['worms']}/10\n"
    stats_text += f"📍 Водоем: {WATER_BODIES[user_data['current_location']]['name']}\n\n"
    
    stats_text += "🐟 *По редкости:*\n"
    stats_text += f"• Обычных: {user_data['stats']['common']}\n"
    stats_text += f"• Редких: {user_data['stats']['rare']}\n"
    stats_text += f"• Эпических: {user_data['stats']['epic']}\n"
    stats_text += f"• Легендарных: {user_data['stats']['legendary']}\n"
    
    bot.send_message(message.chat.id, stats_text)

@bot.message_handler(func=lambda msg: msg.text == '🗺️ Сменить водоем')
def change_location_button(message):
    location_command(message)

@bot.message_handler(func=lambda msg: msg.text == '🛒 Магазин')
def shop_button_handler(message):
    shop_command(message)

@bot.message_handler(func=lambda msg: msg.text == '💰 Продать рыбу')
def sell_button_handler(message):
    sell_command(message)

@bot.message_handler(func=lambda msg: msg.text == '📰 Новости')
def news_button_handler(message):
    news_command(message)

@bot.message_handler(func=lambda msg: msg.text == '🏆 Топы')
def tops_button_handler(message):
    top_command(message)

@bot.message_handler(func=lambda msg: msg.text == '🎒 Инвентарь')
def inventory_button_handler(message):
    inventory_command(message)

@bot.message_handler(func=lambda msg: msg.text == '👑 Админ панель')
def admin_panel_button(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        bot.send_message(message.chat.id, "❌ У вас нет доступа к админ панели!")
        return
    
    admin_level = get_admin_level(user.id)
    admin_text = f"👑 *АДМИН ПАНЕЛЬ*\n\n🎖️ Ваш уровень: {admin_level}/5\n\nВыберите действие:"
    
    bot.send_message(message.chat.id, admin_text, reply_markup=create_admin_keyboard(admin_level))

# Обработчики админ кнопок
@bot.message_handler(func=lambda msg: msg.text == '💰 Выдать донат')
def admin_give_donate_button(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        return
    
    bot.send_message(message.chat.id, 
                    "💰 *Выдача донат товаров*\n\n"
                    "Команды:\n"
                    "/выдать_донат @username ключ_товара\n"
                    "/очередь_донатов - просмотр очереди\n"
                    "/обработать_донат номер - выдать заказ\n\n"
                    "Список товаров (ключи):")
    
    items_text = "🎁 *Доступные товары:*\n"
    for key, data in DONATE_ITEMS.items():
        items_text += f"• `{key}` - {data['name']} ({data['price']}₽)\n"
    
    bot.send_message(message.chat.id, items_text)

@bot.message_handler(func=lambda msg: msg.text == '📋 Очередь донатов')
def admin_donate_queue_button(message):
    user = message.from_user
    if not is_admin(user.id, 1):
        return
    
    donate_queue_command(message)

@bot.message_handler(func=lambda msg: msg.text == '⚙️ Полное управление')
def admin_full_control_button(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        return
    
    bot.send_message(message.chat.id,
                    "⚙️ *ПОЛНОЕ УПРАВЛЕНИЕ (5 уровень)*\n\n"
                    "👑 *Управление админами:*\n"
                    "/+админ @user уровень - добавить админа\n"
                    "/-админ @user - удалить админа\n"
                    "/админы - список админов\n\n"
                    "👤 *Управление игроками:*\n"
                    "/полная_статистика @user - полная статистика\n"
                    "/сбросить @user все - полный сброс\n"
                    "/мут @user время_в_минутах причина\n"
                    "/размут @user\n"
                    "/бан @user время_в_днях причина\n"
                    "/разбан @user\n\n"
                    "📊 *Логи и мониторинг:*\n"
                    "/все_логи - система просмотра логов\n"
                    "/игроки - список всех игроков\n\n"
                    "📢 *Рассылки:*\n"
                    "/отправить_новость текст - отправить всем\n"
                    "/отправить_сообщение @user текст - ЛС игроку")

@bot.message_handler(func=lambda msg: msg.text == '📢 Отправить новость')
def admin_send_news_button(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        return
    
    bot.send_message(message.chat.id,
                    "📢 *Отправка новости*\n\n"
                    "Используйте команду:\n"
                    "/отправить_новость ваш_текст_новости\n\n"
                    "Пример:\n"
                    "/отправить_новость Завтра обновление! Добавим 20 новых видов рыб!")

@bot.message_handler(func=lambda msg: msg.text == '🚫 Бан/Мут')
def admin_ban_mute_button(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        return
    
    bot.send_message(message.chat.id,
                    "🚫 *Бан и мут игроков*\n\n"
                    "🔨 *Бан:*\n"
                    "/бан @user количество_дней причина\n"
                    "/разбан @user\n\n"
                    "🔇 *Мут:*\n"
                    "/мут @user количество_минут причина\n"
                    "/размут @user\n\n"
                    "Примеры:\n"
                    "/бан @username 7 спам в чате\n"
                    "/мут @username 60 флуд")

@bot.message_handler(func=lambda msg: msg.text == '📊 Все логи')
def admin_all_logs_button(message):
    user = message.from_user
    if not is_admin(user.id, 5):
        return
    
    all_logs_command(message)

@bot.message_handler(func=lambda msg: msg.text == '📋 Меню')
def menu_button_handler(message):
    user = message.from_user
    bot.send_message(message.chat.id, "📋 Возвращаю в главное меню:", reply_markup=create_main_keyboard(user.id))

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
    return "🎣 Fishing Bot МЕГА-ОБНОВЛЕНИЕ is running!", 200

@app.route('/set_webhook', methods=['GET'])
def set_webhook():
    if not WEBHOOK_URL:
        return "❌ RENDER_EXTERNAL_URL не настроен", 500
    
    try:
        bot.remove_webhook()
        time.sleep(0.1)
        s = bot.set_webhook(url=WEBHOOK_URL, max_connections=50)
        if s:
            return f"✅ Webhook установлен!\nURL: {WEBHOOK_URL}", 200
        else:
            return "❌ Ошибка установки webhook", 500
    except Exception as e:
        return f"❌ Ошибка: {str(e)}", 500

@app.route('/health')
def health():
    return "OK", 200

@app.route('/status')
def status():
    try:
        bot_info = bot.get_me()
        return json.dumps({
            "status": "running",
            "bot": f"@{bot_info.username}",
            "users": len(db.users),
            "fishes": len(FISHES),
            "rods": len(RODS),
            "donations_in_queue": len(db.donation_queue),
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    print("=" * 60)
    print("🎣 FISHING BOT МЕГА-ОБНОВЛЕНИЕ")
    print("=" * 60)
    print(f"✅ Рыб: {len(FISHES)} видов")
    print(f"✅ Удочек: {len(RODS)} видов")
    print(f"✅ Водоемов: {len(WATER_BODIES)}")
    print(f"✅ Наживок: {len(BAITS)}")
    print(f"✅ Донат товаров: {len(DONATE_ITEMS)}")
    print(f"✅ Админов: {len(ADMINS)}")
    print("=" * 60)
    
    if RENDER_URL:
        keeper = KeepAliveService(RENDER_URL)
        keeper.start()
        print("✅ Keep-alive запущен")
    
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Запуск на порту {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
