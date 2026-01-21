#!/usr/bin/env python3
# bot_fish_complete.py - Полный бот по вашему плану
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
        except Exception as e:
            print(f"❌ Ошибка ping: {type(e).__name__}")

# ========== CONFIGURATION ==========
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8377535372:AAGLMfn_0P_tDvpJnfv_NmW4QclM2AIojEA')
bot = telebot.TeleBot(BOT_TOKEN)

RENDER_URL = os.environ.get('RENDER_EXTERNAL_URL', '')
WEBHOOK_URL = f'{RENDER_URL}/{BOT_TOKEN}' if RENDER_URL else None

# Константы
INITIAL_BASIC_WORMS = 10
MAX_BASIC_WORMS = 10
FISHING_TIME = 30
WORM_REFILL_TIME = 900
WARNING_EXPIRE_TIME = 86400
BAN_DURATION = 172800

# Админы (5 лвл и 1 лвл)
ADMINS = {
    '5330661807': 5,  # 5 лвл - полные права
    '8351629145': 5,  # 5 лвл - полные права  
    '7093049365': 5,  # 5 лвл - полные права
    # Можно добавить админов 1 лвл для доната:
    # '1234567890': 1  # 1 лвл - только донат
}

# ========== БАЗЫ ДАННЫХ ==========
# 1. ВОДОЕМЫ (10 реальных)
WATER_BODIES = [
    {"id": 1, "name": "Онежское озеро", "region": "Карелия", "emoji": "🌊", "depth": "глубокое", "price_entry": 0},
    {"id": 2, "name": "Ладожское озеро", "region": "Лен.область", "emoji": "🏞️", "depth": "очень глубокое", "price_entry": 100},
    {"id": 3, "name": "Река Волга", "region": "Центр России", "emoji": "🌉", "depth": "разная", "price_entry": 50},
    {"id": 4, "name": "Река Енисей", "region": "Сибирь", "emoji": "❄️", "depth": "глубокое", "price_entry": 200},
    {"id": 5, "name": "Озеро Байкал", "region": "Иркутская обл.", "emoji": "💎", "depth": "самое глубокое", "price_entry": 500},
    {"id": 6, "name": "Река Амур", "region": "Дальний Восток", "emoji": "🐉", "depth": "разная", "price_entry": 300},
    {"id": 7, "name": "Река Дон", "region": "Юг России", "emoji": "🌅", "depth": "мелкое", "price_entry": 0},
    {"id": 8, "name": "Река Кубань", "region": "Краснодарский", "emoji": "☀️", "depth": "разная", "price_entry": 100},
    {"id": 9, "name": "Река Обь", "region": "Зап. Сибирь", "emoji": "🌲", "depth": "разная", "price_entry": 150},
    {"id": 10, "name": "Река Кама", "region": "Приволжье", "emoji": "⛰️", "depth": "разная", "price_entry": 50}
]

# 2. НАЖИВКИ (5 видов + обычный червяк)
BAITS = [
    {"id": 1, "name": "Белый опарыш", "emoji": "⚪", "price": 50, "luck": 5, "fish_types": [1,2,3,4,10,26,27]},
    {"id": 2, "name": "Красный опарыш", "emoji": "🔴", "price": 70, "luck": 8, "fish_types": [5,6,7,8,25,28,29]},
    {"id": 3, "name": "Мотыль", "emoji": "🟠", "price": 100, "luck": 12, "fish_types": [9,16,17,19,20,30,31]},
    {"id": 4, "name": "Дождевой червь", "emoji": "🟤", "price": 30, "luck": 3, "fish_types": [11,21,22,23,32,33,34]},
    {"id": 5, "name": "Навозный червь", "emoji": "💩", "price": 40, "luck": 4, "fish_types": [12,13,14,15,18,24,35]},
    {"id": 6, "name": "Обычный червяк", "emoji": "🐛", "price": 0, "luck": 1, "fish_types": "all"}  # Бесплатный
]

# 3. УДОЧКИ (20+ реальных)
RODS = [
    # Поплавочные
    {"id": 1, "name": "Бамбуковая удочка", "type": "поплавочная", "emoji": "🎍", "price": 0, "durability": 100, "luck": 5, "max_weight": 3, "break_chance": 15, "wear_per_fish": 5},
    {"id": 2, "name": "Телескопическая удочка", "type": "поплавочная", "emoji": "📏", "price": 500, "durability": 150, "luck": 8, "max_weight": 5, "break_chance": 12, "wear_per_fish": 4},
    {"id": 3, "name": "Маховая удочка", "type": "поплавочная", "emoji": "🎣", "price": 1000, "durability": 200, "luck": 10, "max_weight": 7, "break_chance": 10, "wear_per_fish": 3},
    
    # Спиннинги
    {"id": 4, "name": "Спиннинг Shimano", "type": "спиннинг", "emoji": "🎣", "price": 3000, "durability": 250, "luck": 15, "max_weight": 10, "break_chance": 8, "wear_per_fish": 4},
    {"id": 5, "name": "Спиннинг Daiwa", "type": "спиннинг", "emoji": "🎣", "price": 5000, "durability": 300, "luck": 18, "max_weight": 15, "break_chance": 7, "wear_per_fish": 3},
    {"id": 6, "name": "Спиннинг Abu Garcia", "type": "спиннинг", "emoji": "🎣", "price": 8000, "durability": 350, "luck": 20, "max_weight": 20, "break_chance": 6, "wear_per_fish": 2},
    {"id": 7, "name": "Кастинговый спиннинг", "type": "спиннинг", "emoji": "🎣", "price": 12000, "durability": 400, "luck": 22, "max_weight": 25, "break_chance": 5, "wear_per_fish": 2},
    
    # Зимние
    {"id": 8, "name": "Зимняя удочка", "type": "зимняя", "emoji": "❄️", "price": 300, "durability": 80, "luck": 6, "max_weight": 2, "break_chance": 20, "wear_per_fish": 6},
    {"id": 9, "name": "Безмотылка", "type": "зимняя", "emoji": "⛄", "price": 800, "durability": 120, "luck": 10, "max_weight": 3, "break_chance": 15, "wear_per_fish": 5},
    {"id": 10, "name": "Зимний спиннинг", "type": "зимняя", "emoji": "🎣", "price": 1500, "durability": 180, "luck": 12, "max_weight": 4, "break_chance": 12, "wear_per_fish": 4},
    
    # Нахлыст
    {"id": 11, "name": "Нахлыстовая удочка", "type": "нахлыст", "emoji": "🎣", "price": 4000, "durability": 220, "luck": 16, "max_weight": 8, "break_chance": 9, "wear_per_fish": 3},
    
    # Карповые
    {"id": 12, "name": "Карповая удочка", "type": "карповая", "emoji": "🐟", "price": 6000, "durability": 450, "luck": 25, "max_weight": 30, "break_chance": 4, "wear_per_fish": 2},
    
    # Морские
    {"id": 13, "name": "Морская удочка", "type": "морская", "emoji": "🌊", "price": 10000, "durability": 500, "luck": 28, "max_weight": 50, "break_chance": 3, "wear_per_fish": 1},
    
    # Премиум
    {"id": 14, "name": "Элитный спиннинг", "type": "спиннинг", "emoji": "🏆", "price": 15000, "durability": 600, "luck": 30, "max_weight": 40, "break_chance": 2, "wear_per_fish": 1},
    {"id": 15, "name": "Профессиональный комплект", "type": "комплект", "emoji": "⭐", "price": 25000, "durability": 800, "luck": 35, "max_weight": 60, "break_chance": 1, "wear_per_fish": 1},
]

# 4. РЫБА (100 видов - реальные из России)
FISHES = [
    # 1-10: Обычные пресноводные
    {"id": 1, "name": "Пескарь", "rarity": "обычная", "min_weight": 50, "max_weight": 150, "emoji": "🐟", "price_per_kg": 500},
    {"id": 2, "name": "Окунь", "rarity": "обычная", "min_weight": 100, "max_weight": 500, "emoji": "🐟", "price_per_kg": 800},
    {"id": 3, "name": "Карась", "rarity": "обычная", "min_weight": 200, "max_weight": 800, "emoji": "🐟", "price_per_kg": 600},
    {"id": 4, "name": "Плотва", "rarity": "обычная", "min_weight": 150, "max_weight": 400, "emoji": "🐟", "price_per_kg": 550},
    {"id": 5, "name": "Ёрш", "rarity": "обычная", "min_weight": 50, "max_weight": 200, "emoji": "🐟", "price_per_kg": 300},
    {"id": 6, "name": "Уклейка", "rarity": "обычная", "min_weight": 30, "max_weight": 100, "emoji": "🐟", "price_per_kg": 400},
    {"id": 7, "name": "Верховка", "rarity": "обычная", "min_weight": 10, "max_weight": 50, "emoji": "🐟", "price_per_kg": 200},
    {"id": 8, "name": "Голец", "rarity": "обычная", "min_weight": 50, "max_weight": 150, "emoji": "🐟", "price_per_kg": 350},
    {"id": 9, "name": "Бычок", "rarity": "обычная", "min_weight": 100, "max_weight": 300, "emoji": "🐟", "price_per_kg": 450},
    {"id": 10, "name": "Колюшка", "rarity": "обычная", "min_weight": 5, "max_weight": 30, "emoji": "🐟", "price_per_kg": 150},
    
    # 11-30: Редкие пресноводные
    {"id": 11, "name": "Щука", "rarity": "редкая", "min_weight": 1000, "max_weight": 8000, "emoji": "🐟", "price_per_kg": 1500},
    {"id": 12, "name": "Судак", "rarity": "редкая", "min_weight": 500, "max_weight": 4000, "emoji": "🐠", "price_per_kg": 2000},
    {"id": 13, "name": "Лещ", "rarity": "редкая", "min_weight": 300, "max_weight": 2000, "emoji": "🐟", "price_per_kg": 1200},
    {"id": 14, "name": "Карп", "rarity": "редкая", "min_weight": 1000, "max_weight": 10000, "emoji": "🐟", "price_per_kg": 1800},
    {"id": 15, "name": "Сазан", "rarity": "редкая", "min_weight": 1500, "max_weight": 12000, "emoji": "🐟", "price_per_kg": 2200},
    {"id": 16, "name": "Жерех", "rarity": "редкая", "min_weight": 800, "max_weight": 3000, "emoji": "🐟", "price_per_kg": 2500},
    {"id": 17, "name": "Голавль", "rarity": "редкая", "min_weight": 400, "max_weight": 2000, "emoji": "🐟", "price_per_kg": 1700},
    {"id": 18, "name": "Язь", "rarity": "редкая", "min_weight": 500, "max_weight": 2500, "emoji": "🐟", "price_per_kg": 1900},
    {"id": 19, "name": "Линь", "rarity": "редкая", "min_weight": 300, "max_weight": 1500, "emoji": "🐟", "price_per_kg": 1600},
    {"id": 20, "name": "Чехонь", "rarity": "редкая", "min_weight": 200, "max_weight": 800, "emoji": "🐟", "price_per_kg": 1400},
    
    # 21-40: Эпические
    {"id": 21, "name": "Сом", "rarity": "эпическая", "min_weight": 5000, "max_weight": 50000, "emoji": "🐠", "price_per_kg": 5000},
    {"id": 22, "name": "Форель", "rarity": "эпическая", "min_weight": 300, "max_weight": 3000, "emoji": "🐠", "price_per_kg": 4000},
    {"id": 23, "name": "Осётр", "rarity": "эпическая", "min_weight": 5000, "max_weight": 30000, "emoji": "🐠", "price_per_kg": 10000},
    {"id": 24, "name": "Белуга", "rarity": "эпическая", "min_weight": 20000, "max_weight": 100000, "emoji": "🐳", "price_per_kg": 15000},
    {"id": 25, "name": "Севрюга", "rarity": "эпическая", "min_weight": 3000, "max_weight": 15000, "emoji": "🐠", "price_per_kg": 8000},
    {"id": 26, "name": "Стерлядь", "rarity": "эпическая", "min_weight": 500, "max_weight": 2000, "emoji": "🐠", "price_per_kg": 12000},
    {"id": 27, "name": "Таймень", "rarity": "эпическая", "min_weight": 3000, "max_weight": 20000, "emoji": "🐟", "price_per_kg": 7000},
    {"id": 28, "name": "Ленок", "rarity": "эпическая", "min_weight": 1000, "max_weight": 5000, "emoji": "🐟", "price_per_kg": 6000},
    {"id": 29, "name": "Нельма", "rarity": "эпическая", "min_weight": 2000, "max_weight": 15000, "emoji": "🐟", "price_per_kg": 9000},
    {"id": 30, "name": "Муксун", "rarity": "эпическая", "min_weight": 1000, "max_weight": 4000, "emoji": "🐟", "price_per_kg": 5500},
    
    # 31-50: Легендарные
    {"id": 31, "name": "Золотая рыбка", "rarity": "легендарная", "min_weight": 100, "max_weight": 300, "emoji": "👑", "price_per_kg": 50000},
    {"id": 32, "name": "Акула белая", "rarity": "легендарная", "min_weight": 50000, "max_weight": 200000, "emoji": "🦈", "price_per_kg": 30000},
    {"id": 33, "name": "Рыба-меч", "rarity": "легендарная", "min_weight": 10000, "max_weight": 80000, "emoji": "⚔️", "price_per_kg": 25000},
    {"id": 34, "name": "Марлин", "rarity": "легендарная", "min_weight": 20000, "max_weight": 150000, "emoji": "🎣", "price_per_kg": 35000},
    {"id": 35, "name": "Тунец голубой", "rarity": "легендарная", "min_weight": 10000, "max_weight": 100000, "emoji": "🐟", "price_per_kg": 28000},
    {"id": 36, "name": "Палтус", "rarity": "легендарная", "min_weight": 5000, "max_weight": 40000, "emoji": "🐟", "price_per_kg": 22000},
    {"id": 37, "name": "Скат манта", "rarity": "легендарная", "min_weight": 10000, "max_weight": 80000, "emoji": "🦋", "price_per_kg": 32000},
    {"id": 38, "name": "Рыба-луна", "rarity": "легендарная", "min_weight": 1000, "max_weight": 2000, "emoji": "🌕", "price_per_kg": 40000},
    {"id": 39, "name": "Баррамунди", "rarity": "легендарная", "min_weight": 3000, "max_weight": 20000, "emoji": "🐟", "price_per_kg": 18000},
    {"id": 40, "name": "Гигантский сом", "rarity": "легендарная", "min_weight": 50000, "max_weight": 300000, "emoji": "🐋", "price_per_kg": 45000},
    
    # 41-60: Морские обычные
    {"id": 41, "name": "Сельдь", "rarity": "обычная", "min_weight": 200, "max_weight": 500, "emoji": "🐟", "price_per_kg": 400},
    {"id": 42, "name": "Камбала", "rarity": "обычная", "min_weight": 300, "max_weight": 1000, "emoji": "🐟", "price_per_kg": 700},
    {"id": 43, "name": "Треска", "rarity": "обычная", "min_weight": 500, "max_weight": 2000, "emoji": "🐟", "price_per_kg": 900},
    {"id": 44, "name": "Мойва", "rarity": "обычная", "min_weight": 30, "max_weight": 100, "emoji": "🐟", "price_per_kg": 300},
    {"id": 45, "name": "Корюшка", "rarity": "обычная", "min_weight": 50, "max_weight": 150, "emoji": "🐟", "price_per_kg": 600},
    {"id": 46, "name": "Скумбрия", "rarity": "обычная", "min_weight": 300, "max_weight": 1000, "emoji": "🐟", "price_per_kg": 800},
    {"id": 47, "name": "Сайра", "rarity": "обычная", "min_weight": 100, "max_weight": 300, "emoji": "🐟", "price_per_kg": 500},
    {"id": 48, "name": "Сардина", "rarity": "обычная", "min_weight": 50, "max_weight": 200, "emoji": "🐟", "price_per_kg": 450},
    {"id": 49, "name": "Ставрида", "rarity": "обычная", "min_weight": 100, "max_weight": 400, "emoji": "🐟", "price_per_kg": 550},
    {"id": 50, "name": "Анчоус", "rarity": "обычная", "min_weight": 20, "max_weight": 80, "emoji": "🐟", "price_per_kg": 350},
    
    # 61-80: Редкие морские
    {"id": 61, "name": "Кета", "rarity": "редкая", "min_weight": 3000, "max_weight": 10000, "emoji": "🐟", "price_per_kg": 3000},
    {"id": 62, "name": "Горбуша", "rarity": "редкая", "min_weight": 1500, "max_weight": 5000, "emoji": "🐟", "price_per_kg": 2500},
    {"id": 63, "name": "Нерка", "rarity": "редкая", "min_weight": 2000, "max_weight": 7000, "emoji": "🐟", "price_per_kg": 3500},
    {"id": 64, "name": "Кижуч", "rarity": "редкая", "min_weight": 3000, "max_weight": 8000, "emoji": "🐟", "price_per_kg": 4000},
    {"id": 65, "name": "Чавыча", "rarity": "редкая", "min_weight": 5000, "max_weight": 15000, "emoji": "🐟", "price_per_kg": 5000},
    {"id": 66, "name": "Сиг", "rarity": "редкая", "min_weight": 500, "max_weight": 2000, "emoji": "🐟", "price_per_kg": 2000},
    {"id": 67, "name": "Ряпушка", "rarity": "редкая", "min_weight": 50, "max_weight": 200, "emoji": "🐟", "price_per_kg": 1500},
    {"id": 68, "name": "Хариус", "rarity": "редкая", "min_weight": 300, "max_weight": 1500, "emoji": "🐟", "price_per_kg": 2800},
    {"id": 69, "name": "Налим", "rarity": "редкая", "min_weight": 500, "max_weight": 3000, "emoji": "🐟", "price_per_kg": 2200},
    {"id": 70, "name": "Угорь", "rarity": "редкая", "min_weight": 300, "max_weight": 2000, "emoji": "🐍", "price_per_kg": 3200},
    
    # 81-100: Разное и мусор
    {"id": 81, "name": "Рак", "rarity": "обычная", "min_weight": 50, "max_weight": 200, "emoji": "🦞", "price_per_kg": 1000},
    {"id": 82, "name": "Креветка", "rarity": "обычная", "min_weight": 10, "max_weight": 50, "emoji": "🦐", "price_per_kg": 800},
    {"id": 83, "name": "Краб", "rarity": "редкая", "min_weight": 300, "max_weight": 1500, "emoji": "🦀", "price_per_kg": 2500},
    {"id": 84, "name": "Мидия", "rarity": "обычная", "min_weight": 30, "max_weight": 100, "emoji": "🐚", "price_per_kg": 400},
    {"id": 85, "name": "Устрица", "rarity": "редкая", "min_weight": 50, "max_weight": 200, "emoji": "🦪", "price_per_kg": 1500},
    {"id": 86, "name": "Кальмар", "rarity": "редкая", "min_weight": 200, "max_weight": 1000, "emoji": "🐙", "price_per_kg": 1800},
    {"id": 87, "name": "Осминог", "rarity": "эпическая", "min_weight": 1000, "max_weight": 5000, "emoji": "🐙", "price_per_kg": 4500},
    {"id": 88, "name": "Медуза", "rarity": "обычная", "min_weight": 100, "max_weight": 500, "emoji": "🪼", "price_per_kg": 200},
    {"id": 89, "name": "Морской конёк", "rarity": "эпическая", "min_weight": 10, "max_weight": 30, "emoji": "🐴", "price_per_kg": 8000},
    {"id": 90, "name": "Иглобрюх", "rarity": "редкая", "min_weight": 300, "max_weight": 1500, "emoji": "🐡", "price_per_kg": 2800},
    
    # 91-100: Мусор и артефакты
    {"id": 91, "name": "Старый ботинок", "rarity": "мусор", "min_weight": 500, "max_weight": 2000, "emoji": "👢", "price_per_kg": 10},
    {"id": 92, "name": "Ржавая банка", "rarity": "мусор", "min_weight": 100, "max_weight": 500, "emoji": "🍺", "price_per_kg": 5},
    {"id": 93, "name": "Пластиковая бутылка", "rarity": "мусор", "min_weight": 50, "max_weight": 200, "emoji": "🧴", "price_per_kg": 2},
    {"id": 94, "name": "Полиэтиленовый пакет", "rarity": "мусор", "min_weight": 10, "max_weight": 100, "emoji": "🗑️", "price_per_kg": 1},
    {"id": 95, "name": "Велосипед", "rarity": "мусор", "min_weight": 10000, "max_weight": 20000, "emoji": "🚲", "price_per_kg": 50},
    {"id": 96, "name": "Автомобильная покрышка", "rarity": "мусор", "min_weight": 5000, "max_weight": 15000, "emoji": "🛞", "price_per_kg": 30},
    {"id": 97, "name": "Рыболовный крючок", "rarity": "мусор", "min_weight": 1, "max_weight": 10, "emoji": "🎣", "price_per_kg": 20},
    {"id": 98, "name": "Снасть", "rarity": "мусор", "min_weight": 50, "max_weight": 300, "emoji": "🎣", "price_per_kg": 40},
    {"id": 99, "name": "Водоросли", "rarity": "мусор", "min_weight": 100, "max_weight": 1000, "emoji": "🌿", "price_per_kg": 3},
    {"id": 100, "name": "Затонувшее сокровище", "rarity": "легендарная", "min_weight": 1000, "max_weight": 5000, "emoji": "💎", "price_per_kg": 100000}
]

# 5. РЕДКОСТИ
RARITY_PROBABILITIES = {
    "обычная": 50,
    "редкая": 30,
    "эпическая": 15,
    "легендарная": 4,
    "мусор": 1
}

# 6. ДОНАТ ПАКЕТЫ
DONATE_PACKAGES = [
    {"id": 1, "name": "🔧 Улучшение удочки", "price": 299, "type": "upgrade", "description": "Удочка не ломается навсегда"},
    {"id": 2, "name": "🍀 Удача +20%", "price": 200, "type": "luck", "description": "Увеличивает шанс удачи на 20%"},
    {"id": 3, "name": "🎣 Спиннинг с удачей 30%", "price": 499, "type": "rod", "description": "Спиннинг Shimano + удача 30%"},
    {"id": 4, "name": "🏆 Рыбопоп 100", "price": 100, "type": "fishpop", "amount": 100},
    {"id": 5, "name": "🏆 Рыбопоп 500", "price": 400, "type": "fishpop", "amount": 500},
    {"id": 6, "name": "🏆 Рыбопоп 1000", "price": 700, "type": "fishpop", "amount": 1000},
    {"id": 7, "name": "🏆 Рыбопоп 5000", "price": 3000, "type": "fishpop", "amount": 5000},
    {"id": 8, "name": "🏆 Рыбопоп 10000", "price": 5000, "type": "fishpop", "amount": 10000},
]

# Номер Тинькофф для доната
TINKOFF_CARD = "2200702034105283"

# Ежедневные задания
DAILY_QUESTIONS = [
    {"question": "🎯 Поймать 5 рыб за день", "reward": 500, "type": "catch_count", "target": 5},
    {"question": "⚖️ Поймать рыбу общим весом 3 кг", "reward": 800, "type": "weight", "target": 3000},
    {"question": "💰 Заработать 1000 рублей", "reward": 1000, "type": "money", "target": 1000},
    {"question": "🌟 Поймать эпическую рыбу", "reward": 1500, "type": "rarity", "target": "эпическая"},
    {"question": "👑 Поймать легендарную рыбу", "reward": 3000, "type": "rarity", "target": "легендарная"},
    {"question": "🎣 Использовать 3 разные наживки", "reward": 600, "type": "bait_variety", "target": 3},
    {"question": "📍 Посетить 3 разных водоема", "reward": 700, "type": "locations", "target": 3},
]

# ========== USER DATABASE ==========
class UserDatabase:
    def __init__(self):
        self.users = {}
        self.active_fishing = {}
        self.news = []
        self.transactions = []
        self.logs = []
        self.daily_tasks = {}  # Для хранения ежедневных заданий
        self.load_data()
    
    def load_data(self):
        try:
            with open('users_data.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.users = data.get('users', {})
                self.news = data.get('news', [])
                self.transactions = data.get('transactions', [])
                self.logs = data.get('logs', [])
                self.daily_tasks = data.get('daily_tasks', {})
            print(f"✅ Загружено {len(self.users)} пользователей, {len(self.news)} новостей")
        except FileNotFoundError:
            print("📁 Файл данных не найден, начинаем с чистого листа")
            self.users = {}
            self.news = []
            self.transactions = []
            self.logs = []
            self.daily_tasks = {}
        except Exception as e:
            print(f"⚠️ Ошибка загрузки данных: {e}")
            self.users = {}
            self.news = []
            self.transactions = []
            self.logs = []
            self.daily_tasks = {}
    
    def save_data(self):
        try:
            data = {
                'users': self.users,
                'news': self.news,
                'transactions': self.transactions,
                'logs': self.logs,
                'daily_tasks': self.daily_tasks
            }
            with open('users_data.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("💾 Данные сохранены")
        except Exception as e:
            print(f"❌ Ошибка сохранения: {e}")
    
    def get_user(self, user_id):
        user_id = str(user_id)
        if user_id not in self.users:
            self.users[user_id] = {
                'worms': INITIAL_BASIC_WORMS,
                'baits': {'6': 10},  # 10 обычных червяков
                'rods': ['1'],
                'active_rod': '1',
                'rod_durability': {'1': 100},
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
                'location': '1',
                'upgrades': {'unbreakable': False, 'luck_boost': 0},
                'daily_task': None,
                'last_daily': None,
                'daily_progress': {},
                'achievements': [],
                'level': 1,
                'exp': 0,
                'messages_sent': 0,
                'referrals': [],
                'referrer': None
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
        log_entry = {
            'timestamp': time.time(),
            'action': action,
            'user_id': str(user_id),
            'admin_id': str(admin_id) if admin_id else None,
            'details': details
        }
        self.logs.append(log_entry)
        if len(self.logs) > 2000:
            self.logs = self.logs[-2000:]
        self.save_data()
    
    def add_news(self, text, author_id):
        news_entry = {
            'id': len(self.news) + 1,
            'text': text,
            'author_id': str(author_id),
            'timestamp': time.time(),
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        self.news.append(news_entry)
        
        # Отправляем новость всем пользователям
        self.broadcast_news(news_entry)
        
        self.save_data()
        return news_entry
    
    def broadcast_news(self, news_entry):
        """Рассылаем новость всем пользователям"""
        news_text = f"📢 *НОВОСТИ*\n\n{news_entry['text']}\n\n📅 {news_entry['date']}"
        
        for user_id in self.users:
            try:
                bot.send_message(user_id, news_text, parse_mode='Markdown')
            except:
                pass  # Пользователь заблокировал бота
    
    def get_news(self, limit=10):
        return sorted(self.news, key=lambda x: x['timestamp'], reverse=True)[:limit]
    
    def add_transaction(self, user_id, package_id, amount, screenshot=None):
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
        for transaction in self.transactions:
            if transaction['id'] == transaction_id:
                transaction['status'] = 'completed'
                transaction['completed_by'] = str(admin_id)
                transaction['completed_at'] = time.time()
                self.save_data()
                return True
        return False
    
    def use_bait(self, user_id):
        user = self.get_user(user_id)
        
        # Собираем все доступные наживки
        available_baits = []
        for bait_id, count in user['baits'].items():
            if count > 0:
                for _ in range(min(count, 3)):  # Макс 3 штуки каждого типа
                    available_baits.append(bait_id)
        
        if not available_baits:
            return None, 0
        
        # Выбираем случайную наживку
        selected_bait = random.choice(available_baits)
        user['baits'][selected_bait] -= 1
        
        self.save_data()
        return selected_bait, user['baits'][selected_bait]
    
    def add_bait(self, user_id, bait_id, amount):
        user = self.get_user(user_id)
        bait_key = str(bait_id)
        user['baits'][bait_key] = user['baits'].get(bait_key, 0) + amount
        self.save_data()
        return user['baits'][bait_key]
    
    def add_rod(self, user_id, rod_id):
        user = self.get_user(user_id)
        rod_str = str(rod_id)
        
        if rod_str not in user['rods']:
            user['rods'].append(rod_str)
            rod_info = next((r for r in RODS if str(r['id']) == rod_str), None)
            if rod_info:
                user['rod_durability'][rod_str] = rod_info['durability']
            self.save_data()
            return True
        return False
    
    def use_rod(self, user_id, fish_weight):
        user = self.get_user(user_id)
        rod_id = user.get('active_rod', '1')
        
        # Если улучшение "вечная удочка"
        if user['upgrades']['unbreakable']:
            return rod_id, user['rod_durability'].get(rod_id, 100), False
        
        rod_info = next((r for r in RODS if str(r['id']) == rod_id), None)
        if not rod_info:
            return rod_id, 100, False
        
        # Проверяем не сломается ли удочка от веса
        max_weight_kg = rod_info['max_weight']
        if fish_weight / 1000 > max_weight_kg * 1.5:  # Если вес превышает на 50%
            # Удочка ломается сразу
            if rod_id in user['rods']:
                user['rods'].remove(rod_id)
            if rod_id in user['rod_durability']:
                del user['rod_durability'][rod_id]
            if user['rods']:
                user['active_rod'] = user['rods'][0]
            else:
                user['active_rod'] = '1'
                user['rods'] = ['1']
                user['rod_durability']['1'] = 100
            self.save_data()
            return rod_id, 0, True
        
        # Обычный износ
        current_durability = user['rod_durability'].get(rod_id, rod_info['durability'])
        wear_amount = rod_info['wear_per_fish']
        new_durability = max(0, current_durability - wear_amount)
        user['rod_durability'][rod_id] = new_durability
        
        broken = False
        if new_durability <= 0:
            if rod_id in user['rods']:
                user['rods'].remove(rod_id)
            if rod_id in user['rod_durability']:
                del user['rod_durability'][rod_id]
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
        user = self.get_user(user_id)
        
        # Рассчитываем стоимость
        value = int((exact_weight / 1000) * fish['price_per_kg'])
        
        catch = {
            'fish_id': fish['id'],
            'name': fish['name'],
            'rarity': fish['rarity'],
            'weight': exact_weight,
            'value': value,
            'emoji': fish['emoji'],
            'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'location': user.get('location', '1')
        }
        
        user['fish_caught'].append(catch)
        if len(user['fish_caught']) > 100:
            user['fish_caught'] = user['fish_caught'][-100:]
        
        user['total_fish'] += 1
        user['total_weight'] += exact_weight
        user['money'] += value
        
        # Опыт
        exp_gained = max(1, value // 100)
        user['exp'] += exp_gained
        
        # Проверка уровня
        level_up = False
        exp_needed = user['level'] * 1000
        if user['exp'] >= exp_needed:
            user['level'] += 1
            user['exp'] = user['exp'] - exp_needed
            level_up = True
        
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
        
        # Проверка ежедневного задания
        self.check_daily_task(user_id, catch)
        
        self.save_data()
        return catch, level_up, exp_gained
    
    def check_daily_task(self, user_id, catch):
        """Проверка выполнения ежедневного задания"""
        user = self.get_user(user_id)
        
        if not user.get('daily_task'):
            return
        
        task = user['daily_task']
        progress = user.get('daily_progress', {})
        
        if task['type'] == 'catch_count':
            progress['count'] = progress.get('count', 0) + 1
            if progress['count'] >= task['target']:
                self.complete_daily_task(user_id)
        
        elif task['type'] == 'weight':
            progress['weight'] = progress.get('weight', 0) + catch['weight']
            if progress['weight'] >= task['target']:
                self.complete_daily_task(user_id)
        
        elif task['type'] == 'money':
            # Проверяется при добавлении денег в add_fish
            pass
        
        elif task['type'] == 'rarity':
            if catch['rarity'] == task['target']:
                self.complete_daily_task(user_id)
        
        user['daily_progress'] = progress
        self.save_data()
    
    def complete_daily_task(self, user_id):
        """Завершение ежедневного задания"""
        user = self.get_user(user_id)
        if not user.get('daily_task'):
            return
        
        task = user['daily_task']
        reward = task['reward']
        
        user['money'] += reward
        user['daily_task'] = None
        user['daily_progress'] = {}
        user['last_daily'] = time.time()
        
        # Отправляем уведомление
        try:
            bot.send_message(user_id, 
                           f"🎉 *Ежедневное задание выполнено!*\n\n"
                           f"🏆 Награда: {reward} руб\n"
                           f"💰 Теперь у вас: {user['money']} руб")
        except:
            pass
        
        self.save_data()
    
    def assign_daily_task(self, user_id):
        """Выдача нового ежедневного задания"""
        user = self.get_user(user_id)
        
        # Проверяем, можно ли выдать новое задание
        last_daily = user.get('last_daily')
        if last_daily:
            current_time = time.time()
            if current_time - last_daily < 86400:  # 24 часа
                return False
        
        # Выбираем случайное задание
        task = random.choice(DAILY_QUESTIONS)
        user['daily_task'] = task
        user['daily_progress'] = {}
        user['last_daily'] = time.time()
        
        self.save_data()
        
        # Отправляем задание
        try:
            bot.send_message(user_id,
                           f"📅 *Новое ежедневное задание!*\n\n"
                           f"🎯 {task['question']}\n"
                           f"🏆 Награда: {task['reward']} руб\n\n"
                           f"Удачи! 🎣")
        except:
            pass
        
        return True
    
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
    
    def get_top_players(self, by='fish', limit=20):
        players = []
        
        for user_id, user_data in self.users.items():
            if by == 'fish':
                score = user_data.get('total_fish', 0)
            elif by == 'weight':
                score = user_data.get('total_weight', 0)
            elif by == 'money':
                score = user_data.get('money', 0)
            elif by == 'fishpop':
                score = user_data.get('fishpop', 0)
            elif by == 'level':
                score = user_data.get('level', 1)
            else:
                score = 0
            
            players.append({
                'user_id': user_id,
                'username': user_data.get('username', 'Неизвестно'),
                'first_name': user_data.get('first_name', 'Игрок'),
                'score': score
            })
        
        return sorted(players, key=lambda x: x['score'], reverse=True)[:limit]
    
    def get_user_stats(self, user_id):
        """Полная статистика пользователя"""
        user = self.get_user(user_id)
        
        stats = {
            'user_id': user_id,
            'username': user.get('username'),
            'first_name': user.get('first_name'),
            'level': user.get('level', 1),
            'exp': user.get('exp', 0),
            'money': user.get('money', 0),
            'fishpop': user.get('fishpop', 0),
            'total_fish': user.get('total_fish', 0),
            'total_weight': user.get('total_weight', 0),
            'stats': user.get('stats', {}),
            'warnings': len([w for w in user.get('warnings', []) if time.time() - w < WARNING_EXPIRE_TIME]),
            'banned': user.get('banned_until') is not None and time.time() < user.get('banned_until', 0),
            'banned_until': user.get('banned_until'),
            'upgrades': user.get('upgrades', {}),
            'rods_count': len(user.get('rods', [])),
            'location': user.get('location', '1'),
            'daily_task': user.get('daily_task'),
            'last_fishing': user.get('last_fishing_time'),
            'register_date': min(user.get('warnings', []) + [time.time()]) if user.get('warnings') else time.time()
        }
        
        return stats

db = UserDatabase()

# ========== ОСНОВНЫЕ ФУНКЦИИ ==========
def calculate_catch(bait_id, location_id, user_luck=0):
    """Рассчитываем улов с учетом всех факторов"""
    
    # Базовая вероятность редкости с учетом удачи
    base_probs = RARITY_PROBABILITIES.copy()
    
    # Увеличиваем шанс на эпическую и легендарную в зависимости от удачи
    luck_bonus = user_luck
    base_probs["эпическая"] = max(5, base_probs["эпическая"] + luck_bonus * 0.5)
    base_probs["легендарная"] = max(1, base_probs["легендарная"] + luck_bonus * 0.2)
    base_probs["обычная"] = max(20, base_probs["обычная"] - luck_bonus * 0.7)
    
    # Нормализуем вероятности
    total = sum(base_probs.values())
    rand_num = random.uniform(0, total)
    
    current = 0
    selected_rarity = "обычная"
    for rarity, prob in base_probs.items():
        current += prob
        if rand_num <= current:
            selected_rarity = rarity
            break
    
    # Получаем наживку
    bait_info = next((b for b in BAITS if str(b['id']) == str(bait_id)), BAITS[-1])
    
    # Фильтруем рыбу по редкости
    available_fish = [f for f in FISHES if f['rarity'] == selected_rarity]
    
    if not available_fish:
        available_fish = [f for f in FISHES if f['rarity'] == "обычная"]
    
    # Если у наживки есть предпочтения, увеличиваем шанс этой рыбы
    if bait_info.get('fish_types') != "all":
        preferred_fish = [f for f in available_fish if f['id'] in bait_info['fish_types']]
        if preferred_fish:
            # 70% шанс получить предпочитаемую рыбу
            if random.random() < 0.7:
                available_fish = preferred_fish
    
    # Выбираем случайную рыбу
    selected_fish = random.choice(available_fish)
    
    # Генерируем точный вес
    min_w = selected_fish['min_weight']
    max_w = selected_fish['max_weight']
    
    # Вес зависит от удачи (больше удача = больше вес)
    weight_multiplier = 1.0 + (user_luck / 100)
    adjusted_max = int(max_w * weight_multiplier)
    exact_weight = random.randint(min_w, min(adjusted_max, max_w * 2))
    
    return selected_fish, exact_weight

# ========== КЛАВИАТУРЫ ==========
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
    btn9 = types.KeyboardButton('🎯 Ежедневное задание')
    btn10 = types.KeyboardButton('❓ Помощь')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6, btn7, btn8, btn9, btn10)
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
        btn9 = types.KeyboardButton('🔍 Статистика игрока')
        btn10 = types.KeyboardButton('🔄 Сбросить прогресс')
        markup.add(btn3, btn4, btn5, btn6, btn7, btn8, btn9, btn10)
    
    btn_back = types.KeyboardButton('⬅️ В меню')
    markup.add(btn_back)
    return markup

# ========== СИСТЕМА ПРЕДУПРЕЖДЕНИЙ И БАНОВ ==========
def delete_links_in_group(message):
    if message.chat.type in ['group', 'supergroup']:
        text = message.text or message.caption or ""
        
        if 'http' in text.lower() or 'www.' in text.lower() or '.com' in text.lower() or '.ru' in text.lower():
            user = message.from_user
            user_id = str(user.id)
            chat_id = message.chat.id
            
            if db.is_banned(user_id):
                return True
            
            try:
                bot.delete_message(chat_id, message.message_id)
            except:
                pass
            
            banned, warning_count, is_ban = db.add_warning(user_id, chat_id)
            
            if is_ban:
                try:
                    bot.ban_chat_member(chat_id, user.id, until_date=int(time.time()) + BAN_DURATION)
                    ban_msg = f"🚫 {user.first_name} забанен на 2 дня за ссылки!"
                    bot.send_message(chat_id, ban_msg)
                except:
                    pass
            else:
                warn_msg = f"⚠️ {user.first_name}, предупреждение за ссылку!\n{warning_count}/2 до бана"
                bot.send_message(chat_id, warn_msg)
            
            return True
    return False

# ========== КОМАНДА START ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    user_id_str = str(user.id)
    user_data = db.get_user(user.id)
    
    # Обновляем имя
    user_data['username'] = user.username
    user_data['first_name'] = user.first_name
    user_data['messages_sent'] = user_data.get('messages_sent', 0) + 1
    
    if db.is_banned(user_id_str):
        ban_time = db.get_ban_time_left(user.id)
        days = int(ban_time // 86400)
        hours = int((ban_time % 86400) // 3600)
        minutes = int((ban_time % 3600) // 60)
        
        ban_text = f"🚫 Вы забанены!\n⏳ Осталось: {days}д {hours}ч {minutes}м"
        bot.send_message(message.chat.id, ban_text)
        return
    
    # Проверяем админку
    admin_level = ADMINS.get(user_id_str, 0)
    
    welcome_text = (
        f"🎣 *Добро пожаловать, {user.first_name}!*\n\n"
        f"📍 Текущий водоем: {WATER_BODIES[int(user_data.get('location', 1))-1]['name']}\n"
        f"🎣 Удочка: {next((r['name'] for r in RODS if str(r['id']) == user_data.get('active_rod', '1')), 'Базовая')}\n"
        f"🪱 Наживка: {sum(user_data['baits'].values())} шт\n"
        f"💰 Деньги: {user_data['money']} руб | 🏆 Уровень: {user_data.get('level', 1)}\n\n"
        f"🎮 *Используйте кнопки для игры:*\n"
        f"• 🎣 Начать рыбалку - поймать рыбу\n"
        f"• 📍 Сменить водоем - 10 разных мест\n"
        f"• 🛒 Магазин - купить снасти\n"
        f"• 🏆 Топ игроков - посмотреть рейтинги\n"
        f"• 📰 Новости - последние обновления\n"
        f"• 💰 Донат - поддержать проект\n"
        f"• 🎯 Ежедневное задание - получить награду\n\n"
        f"💳 Поддержка: ||{TINKOFF_CARD}||\n"
        f"📢 Новости: /news"
    )
    
    if admin_level > 0:
        welcome_text += f"\n\n👑 Уровень админа: {admin_level}"
        bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown',
                        reply_markup=create_admin_keyboard(admin_level))
    else:
        bot.send_message(message.chat.id, welcome_text, parse_mode='Markdown',
                        reply_markup=create_main_keyboard())
    
    # Логируем
    db.add_log('start', user.id, f"Пользователь зашел в бота")

# ========== КОМАНДА NEWS (для админов 5 лвл) ==========
@bot.message_handler(commands=['news'])
def news_command(message):
    """Отправить новость всем игрокам (только админы 5 лвл)"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 5:
        bot.reply_to(message, "❌ Только для админов 5 лвл")
        return
    
    # Проверяем есть ли текст
    parts = message.text.split(' ', 1)
    if len(parts) < 2:
        bot.reply_to(message, "❌ Использование: /news текст новости")
        return
    
    news_text = parts[1]
    
    # Добавляем новость
    news_entry = db.add_news(news_text, user.id)
    
    bot.reply_to(message,
                f"✅ Новость отправлена всем игрокам!\n\n"
                f"📅 {news_entry['date']}\n"
                f"👤 Автор: {user.first_name}\n"
                f"📊 Игроков: {len(db.users)}")

# ========== КОМАНДА TOP ==========
@bot.message_handler(commands=['top'])
def top_command(message):
    user = message.from_user
    if db.is_banned(str(user.id)):
        return
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🐟 По рыбе", callback_data="top_fish")
    btn2 = types.InlineKeyboardButton("⚖️ По весу", callback_data="top_weight")
    btn3 = types.InlineKeyboardButton("💰 По деньгам", callback_data="top_money")
    btn4 = types.InlineKeyboardButton("🏆 По уровню", callback_data="top_level")
    markup.add(btn1, btn2, btn3, btn4)
    
    bot.send_message(message.chat.id, "🏆 *Топ игроков*\nВыберите категорию:",
                    parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('top_'))
def handle_top_callback(call):
    top_type = call.data.split('_')[1]
    
    if top_type == 'fish':
        top_data = db.get_top_players('fish', 20)
        title = "🐟 Топ-20 по количеству рыбы"
        emoji = "🐟"
    elif top_type == 'weight':
        top_data = db.get_top_players('weight', 20)
        title = "⚖️ Топ-20 по общему весу"
        emoji = "⚖️"
    elif top_type == 'money':
        top_data = db.get_top_players('money', 20)
        title = "💰 Топ-20 по деньгам"
        emoji = "💰"
    else:  # level
        top_data = db.get_top_players('level', 20)
        title = "🏆 Топ-20 по уровню"
        emoji = "🏆"
    
    top_text = f"*{title}*\n\n"
    
    medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣', '7️⃣', '8️⃣', '9️⃣', '🔟',
              '1️⃣1️⃣', '1️⃣2️⃣', '1️⃣3️⃣', '1️⃣4️⃣', '1️⃣5️⃣', '1️⃣6️⃣', '1️⃣7️⃣', '1️⃣8️⃣', '1️⃣9️⃣', '2️⃣0️⃣']
    
    for i, player in enumerate(top_data, 1):
        username = player['username'] if player['username'] else player['first_name']
        score = player['score']
        
        if top_type == 'weight':
            score_text = f"{score/1000:.1f} кг"
        elif top_type == 'money':
            score_text = f"{score} руб"
        else:
            score_text = str(score)
        
        medal = medals[i-1] if i <= len(medals) else f"{i}."
        
        top_text += f"{medal} {username}: {score_text}\n"
    
    if not top_data:
        top_text = "📭 Пока нет данных для топа"
    
    try:
        bot.edit_message_text(top_text, call.message.chat.id, call.message.message_id,
                            parse_mode='Markdown')
    except:
        bot.send_message(call.message.chat.id, top_text, parse_mode='Markdown')

# ========== РЫБАЛКА ==========
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
        bot.send_message(message.chat.id, "⏳ Вы уже рыбачите! Подождите...",
                        reply_markup=create_fishing_keyboard())
        return
    
    user_data = db.get_user(user.id)
    
    # Проверяем наживку
    total_baits = sum(user_data['baits'].values())
    if total_baits <= 0:
        bot.send_message(message.chat.id,
                        "😔 Наживка закончилась!\n"
                        "Купите в магазине или подождите пополнения.",
                        reply_markup=create_main_keyboard())
        return
    
    # Начинаем рыбалку
    msg = bot.send_message(message.chat.id,
                          f"🎣 *Начинаем рыбалку!*\n\n"
                          f"📍 Водоем: {WATER_BODIES[int(user_data.get('location', 1))-1]['name']}\n"
                          f"🎣 Удочка: {next((r['name'] for r in RODS if str(r['id']) == user_data.get('active_rod', '1')), 'Базовая')}\n"
                          f"⏳ Ждите {FISHING_TIME} секунд...",
                          reply_markup=create_fishing_keyboard())
    
    def fishing_timer():
        time.sleep(FISHING_TIME)
        
        if user_id not in db.active_fishing:
            return
        
        del db.active_fishing[user_id]
        
        # Используем наживку
        bait_id, bait_left = db.use_bait(user.id)
        bait_info = next((b for b in BAITS if str(b['id']) == bait_id), BAITS[-1])
        
        # Получаем данные пользователя
        user_data = db.get_user(user.id)
        location_id = user_data.get('location', '1')
        user_luck = user_data['upgrades'].get('luck_boost', 0)
        
        # Рассчитываем улов
        fish, exact_weight = calculate_catch(bait_id, location_id, user_luck)
        
        # Проверяем удочку
        rod_id, durability, broken = db.use_rod(user.id, exact_weight)
        rod_info = next((r for r in RODS if str(r['id']) == rod_id), RODS[0])
        
        # Добавляем рыбу
        catch_info, level_up, exp_gained = db.add_fish(user.id, fish, exact_weight)
        
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
            f"📦 Осталось: {bait_left} шт\n\n"
            f"{rarity_emojis.get(fish['rarity'], '🎣')} *Поймано:* {fish['name']}\n"
            f"⚖️ *Вес:* {exact_weight} г ({exact_weight/1000:.2f} кг)\n"
            f"💰 *Стоимость:* {catch_info['value']} руб\n"
            f"📊 *Редкость:* {fish['rarity']}\n\n"
            f"🎣 Удочка: {rod_info['name']}\n"
            f"🔧 Прочность: {durability}/{rod_info['durability']}\n"
            f"💰 Баланс: {db.get_user(user.id)['money']} руб\n"
            f"🏆 Опыт: +{exp_gained}\n"
        )
        
        if level_up:
            result_text += f"\n🎊 *УРОВЕНЬ ПОВЫШЕН!* Новый уровень: {user_data['level']} 🎊\n"
        
        if broken:
            result_text += "\n⚠️ *Удочка сломалась!* Купите новую в магазине.\n"
        
        if fish['rarity'] == 'легендарная':
            result_text += "\n🎊 *ВАУ! Легендарная рыба!* 🎊\n"
        elif fish['rarity'] == 'мусор':
            result_text += "\n😔 Не повезло... Попробуйте еще раз!\n"
        
        if durability < rod_info['durability'] * 0.3:
            result_text += f"\n🔴 *Внимание!* Удочка почти сломана ({durability}%). Ремонтируйте!\n"
        
        try:
            bot.send_message(message.chat.id, result_text, parse_mode='Markdown',
                           reply_markup=create_main_keyboard())
        except Exception as e:
            print(f"Ошибка отправки: {e}")
    
    db.active_fishing[user_id] = threading.Thread(target=fishing_timer)
    db.active_fishing[user_id].daemon = True
    db.active_fishing[user_id].start()

# ========== МАГАЗИН ==========
@bot.message_handler(func=lambda msg: msg.text == '🛒 Магазин')
def shop_button_handler(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    shop_text = (
        f"🛒 *Магазин снастей*\n\n"
        f"💰 Баланс: {user_data['money']} руб\n"
        f"🏆 Рыбопоп: {user_data.get('fishpop', 0)}\n\n"
        f"Выберите категорию:"
    )
    
    bot.send_message(message.chat.id, shop_text, parse_mode='Markdown',
                    reply_markup=create_shop_keyboard())

@bot.message_handler(func=lambda msg: msg.text == '🪱 Купить наживку')
def buy_bait_handler(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for bait in BAITS:
        if bait['price'] > 0:
            btn_text = f"{bait['emoji']} {bait['name']} - {bait['price']} руб"
            callback_data = f"buy_bait_{bait['id']}"
            markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    bait_text = (
        f"🪱 *Купить наживку*\n\n"
        f"💰 Баланс: {user_data['money']} руб\n\n"
        f"*Доступная наживка:*\n"
    )
    
    for bait in BAITS:
        if bait['price'] > 0:
            current_count = user_data['baits'].get(str(bait['id']), 0)
            bait_text += f"\n{bait['emoji']} *{bait['name']}*\n"
            bait_text += f"  💰 Цена: {bait['price']} руб | 🍀 Удача: +{bait['luck']}%\n"
            bait_text += f"  📦 У вас: {current_count} шт\n"
    
    bot.send_message(message.chat.id, bait_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('buy_bait_'))
def handle_buy_bait(call):
    user = call.from_user
    bait_id = call.data.split('_')[2]
    
    user_data = db.get_user(user.id)
    bait_info = next((b for b in BAITS if str(b['id']) == bait_id), None)
    
    if not bait_info or bait_info['price'] <= 0:
        bot.answer_callback_query(call.id, "❌ Наживка не найдена")
        return
    
    if user_data['money'] < bait_info['price']:
        bot.answer_callback_query(call.id, "❌ Недостаточно денег")
        return
    
    # Покупаем
    user_data['money'] -= bait_info['price']
    new_count = db.add_bait(user.id, bait_id, 1)
    
    # Логируем
    db.add_log('buy_bait', user.id, f"{bait_info['name']} за {bait_info['price']} руб")
    
    response = (
        f"✅ *Куплено!*\n\n"
        f"🪱 {bait_info['emoji']} {bait_info['name']}\n"
        f"💰 Цена: {bait_info['price']} руб\n"
        f"📦 Теперь у вас: {new_count} шт\n"
        f"💳 Осталось: {user_data['money']} руб"
    )
    
    try:
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id,
                            parse_mode='Markdown')
    except:
        bot.send_message(call.message.chat.id, response, parse_mode='Markdown')
    
    bot.answer_callback_query(call.id, "✅ Куплено!")

# ========== ДОНАТ СИСТЕМА ==========
@bot.message_handler(func=lambda msg: msg.text == '💰 Донат')
def donate_handler(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    for package in DONATE_PACKAGES:
        btn_text = f"{package['name']} - {package['price']} руб"
        callback_data = f"donate_{package['id']}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=callback_data))
    
    donate_text = (
        f"💰 *Поддержать проект*\n\n"
        f"💳 *Тинькофф карта:*\n"
        f"`{TINKOFF_CARD}`\n\n"
        f"*Как получить награду:*\n"
        f"1. Выберите пакет\n"
        f"2. Переведите сумму на карту\n"
        f"3. Отправьте скриншот чека\n"
        f"4. Получите награду в течение 24ч\n\n"
        f"*Выберите пакет:*"
    )
    
    bot.send_message(message.chat.id, donate_text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('donate_'))
def handle_donate_select(call):
    package_id = int(call.data.split('_')[1])
    package = next((p for p in DONATE_PACKAGES if p['id'] == package_id), None)
    
    if not package:
        bot.answer_callback_query(call.id, "❌ Пакет не найден")
        return
    
    donate_text = (
        f"🎁 *Пакет: {package['name']}*\n\n"
        f"💰 Цена: {package['price']} руб\n"
    )
    
    if package['type'] == 'upgrade':
        donate_text += f"📝 {package['description']}\n\n"
    elif package['type'] == 'luck':
        donate_text += f"📝 {package['description']}\n\n"
    elif package['type'] == 'rod':
        donate_text += f"📝 {package['description']}\n\n"
    elif package['type'] == 'fishpop':
        donate_text += f"🎁 Награда: {package['amount']} рыбопоп\n\n"
    
    donate_text += f"💳 *Для оплаты:*\n"
    donate_text += f"Переведите *{package['price']} руб* на карту:\n"
    donate_text += f"`{TINKOFF_CARD}`\n\n"
    donate_text += f"📸 *После перевода:*\n"
    donate_text += f"1. Сделайте скриншот чека\n"
    donate_text += f"2. Отправьте его сюда\n"
    donate_text += f"3. В подписи укажите: Донат #{package_id}\n\n"
    donate_text += f"⏳ Награда будет выдана в течение 24 часов"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✅ Я оплатил, отправить чек", 
                                         callback_data=f"confirm_pay_{package_id}"))
    
    try:
        bot.edit_message_text(donate_text, call.message.chat.id, call.message.message_id,
                            parse_mode='Markdown', reply_markup=markup)
    except:
        bot.send_message(call.message.chat.id, donate_text, parse_mode='Markdown',
                        reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('confirm_pay_'))
def handle_confirm_payment(call):
    package_id = int(call.data.split('_')[2])
    package = next((p for p in DONATE_PACKAGES if p['id'] == package_id), None)
    
    if not package:
        bot.answer_callback_query(call.id, "❌ Пакет не найден")
        return
    
    bot.answer_callback_query(call.id, "📸 Теперь отправьте скриншот чека")
    
    bot.send_message(call.message.chat.id,
                    f"📸 *Ожидаю чек об оплате*\n\n"
                    f"Пакет: {package['name']}\n"
                    f"Сумма: {package['price']} руб\n\n"
                    f"Отправьте скриншот чека.\n"
                    f"В подписи укажите: Донат #{package_id}",
                    parse_mode='Markdown')

@bot.message_handler(content_types=['photo'])
def handle_donate_screenshot(message):
    user = message.from_user
    caption = message.caption or ""
    
    # Ищем номер пакета
    import re
    match = re.search(r'#(\d+)', caption)
    if not match:
        bot.reply_to(message, "❌ В подписи укажите номер пакета: Донат #<номер>")
        return
    
    package_id = int(match.group(1))
    package = next((p for p in DONATE_PACKAGES if p['id'] == package_id), None)
    
    if not package:
        bot.reply_to(message, "❌ Пакет не найден")
        return
    
    # Создаем транзакцию
    transaction = db.add_transaction(user.id, package_id, package['price'], 
                                    screenshot=message.photo[-1].file_id)
    
    # Отправляем админам
    admin_message = (
        f"🤑 *Новый донат!*\n\n"
        f"👤 Пользователь: @{user.username or user.first_name}\n"
        f"🆔 ID: {user.id}\n"
        f"🎁 Пакет: {package['name']}\n"
        f"💰 Сумма: {package['price']} руб\n"
        f"📋 ID транзакции: {transaction['id']}\n\n"
        f"Для выдачи награды:\n"
        f"/donate_complete {transaction['id']}"
    )
    
    # Отправляем всем админам 5 лвл
    for admin_id_str, level in ADMINS.items():
        if level >= 5:
            try:
                bot.send_photo(admin_id_str, message.photo[-1].file_id,
                             caption=admin_message, parse_mode='Markdown')
            except:
                pass
    
    # Ответ пользователю
    bot.reply_to(message,
                f"✅ *Чек получен!*\n\n"
                f"📋 ID транзакции: {transaction['id']}\n"
                f"⏳ Модераторы проверят перевод и выдадут награду.")

# ========== АДМИН КОМАНДЫ ==========
@bot.message_handler(commands=['donate_complete'])
def donate_complete_command(message):
    """Завершение транзакции доната"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 1:
        bot.reply_to(message, "❌ Только для админов")
        return
    
    try:
        transaction_id = int(message.text.split()[1])
    except:
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
    
    # Завершаем
    if db.complete_transaction(transaction_id, user.id):
        # Выдаем награду
        package = next((p for p in DONATE_PACKAGES if p['id'] == transaction['package_id']), None)
        target_user_id = transaction['user_id']
        user_data = db.get_user(target_user_id)
        
        if package['type'] == 'upgrade':
            user_data['upgrades']['unbreakable'] = True
            reward_text = "🔧 Удочка не ломается навсегда"
        
        elif package['type'] == 'luck':
            user_data['upgrades']['luck_boost'] = user_data['upgrades'].get('luck_boost', 0) + 20
            reward_text = "🍀 Удача +20%"
        
        elif package['type'] == 'rod':
            db.add_rod(target_user_id, 4)  # Спиннинг Shimano
            user_data['upgrades']['luck_boost'] = user_data['upgrades'].get('luck_boost', 0) + 30
            reward_text = "🎣 Спиннинг Shimano + удача 30%"
        
        elif package['type'] == 'fishpop':
            user_data['fishpop'] = user_data.get('fishpop', 0) + package['amount']
            reward_text = f"🏆 {package['amount']} рыбопоп"
        
        db.save_data()
        
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
            pass
        
        # Логируем
        db.add_log('donate_complete', target_user_id, 
                  f"{package['name']} за {package['price']} руб", user.id)
        
    else:
        bot.reply_to(message, "❌ Ошибка при завершении транзакции")

@bot.message_handler(commands=['donate_list'])
def donate_list_command(message):
    """Список ожидающих транзакций"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 1:
        bot.reply_to(message, "❌ Только для админов")
        return
    
    pending = [t for t in db.transactions if t['status'] == 'pending']
    
    if not pending:
        bot.reply_to(message, "✅ Нет ожидающих транзакций")
        return
    
    text = "📋 *Ожидающие транзакции:*\n\n"
    
    for t in pending[-10:]:
        package = next((p for p in DONATE_PACKAGES if p['id'] == t['package_id']), None)
        date = datetime.fromtimestamp(t['timestamp']).strftime("%d.%m %H:%M")
        
        text += f"📋 *ID:* {t['id']}\n"
        text += f"👤 Пользователь: {t['user_id']}\n"
        text += f"🎁 Пакет: {package['name'] if package else 'Неизвестно'}\n"
        text += f"💰 Сумма: {t['amount']} руб\n"
        text += f"📅 Дата: {date}\n"
        text += f"✅ Для выдачи: /donate_complete {t['id']}\n"
        text += "─" * 30 + "\n\n"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '👑 Админ панель')
def admin_panel_handler(message):
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
        f"💰 Транзакций: {len([t for t in db.transactions if t['status'] == 'pending'])} ожидают\n\n"
    )
    
    if admin_level >= 5:
        admin_text += "*Полные права (5 лвл):*\n"
        admin_text += "• Выдача наград\n"
        admin_text += "• Предупреждения и баны\n"
        admin_text += "• Отправка новостей\n"
        admin_text += "• Просмотр логов\n"
        admin_text += "• Статистика игроков\n"
        admin_text += "• Сброс прогресса\n"
    
    if admin_level >= 1:
        admin_text += "\n*Права доната (1 лвл):*\n"
        admin_text += "• Обработка транзакций\n"
        admin_text += "• Выдача донат-наград\n"
    
    bot.send_message(message.chat.id, admin_text, parse_mode='Markdown',
                    reply_markup=create_admin_keyboard(admin_level))

@bot.message_handler(func=lambda msg: msg.text == '📋 Список игроков')
def admin_players_handler(message):
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 1:
        bot.reply_to(message, "❌ Недостаточно прав")
        return
    
    # Получаем всех игроков
    players = []
    for uid, user_data in db.users.items():
        players.append({
            'id': uid,
            'username': user_data.get('username', 'Неизвестно'),
            'first_name': user_data.get('first_name', 'Игрок'),
            'level': user_data.get('level', 1),
            'fish': user_data.get('total_fish', 0)
        })
    
    # Сортируем по уровню
    players = sorted(players, key=lambda x: x['level'], reverse=True)
    
    # Разбиваем на страницы
    page_size = 10
    total_pages = (len(players) + page_size - 1) // page_size
    
    # Создаем inline клавиатуру
    markup = types.InlineKeyboardMarkup()
    
    if total_pages > 1:
        row = []
        pages_to_show = min(5, total_pages)
        for i in range(1, pages_to_show + 1):
            row.append(types.InlineKeyboardButton(str(i), callback_data=f"players_page_{i}"))
        markup.row(*row)
        
        if total_pages > 5:
            markup.row(types.InlineKeyboardButton("➡️", callback_data=f"players_page_{min(6, total_pages)}"))
    
    # Показываем первую страницу
    show_players_page(message.chat.id, 1, players, page_size, markup)

def show_players_page(chat_id, page_num, players, page_size, markup):
    start = (page_num - 1) * page_size
    end = start + page_size
    page_players = players[start:end]
    
    text = f"📋 *Список игроков (стр. {page_num})*\n\n"
    
    for i, player in enumerate(page_players, start + 1):
        text += f"{i}. @{player['username']} ({player['first_name']})\n"
        text += f"   🆔: {player['id']} | 🏆 Ур. {player['level']} | 🐟 {player['fish']}\n\n"
    
    if not page_players:
        text = "📭 Нет игроков"
    
    bot.send_message(chat_id, text, parse_mode='Markdown', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('players_page_'))
def handle_players_page(call):
    page_num = int(call.data.split('_')[2])
    
    # Перезагружаем список
    players = []
    for uid, user_data in db.users.items():
        players.append({
            'id': uid,
            'username': user_data.get('username', 'Неизвестно'),
            'first_name': user_data.get('first_name', 'Игрок'),
            'level': user_data.get('level', 1),
            'fish': user_data.get('total_fish', 0)
        })
    
    players = sorted(players, key=lambda x: x['level'], reverse=True)
    page_size = 10
    total_pages = (len(players) + page_size - 1) // page_size
    
    # Обновляем клавиатуру
    markup = types.InlineKeyboardMarkup()
    if total_pages > 1:
        row = []
        start_page = max(1, page_num - 2)
        end_page = min(total_pages, page_num + 2)
        
        if page_num > 1:
            markup.row(types.InlineKeyboardButton("⬅️", callback_data=f"players_page_{page_num-1}"))
        
        for i in range(start_page, end_page + 1):
            row.append(types.InlineKeyboardButton(str(i), callback_data=f"players_page_{i}"))
        
        if row:
            markup.row(*row)
        
        if page_num < total_pages:
            markup.row(types.InlineKeyboardButton("➡️", callback_data=f"players_page_{page_num+1}"))
    
    show_players_page(call.message.chat.id, page_num, players, page_size, markup)
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda msg: msg.text == '🔍 Статистика игрока')
def admin_player_stats_handler(message):
    """Статистика конкретного игрока"""
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 5:
        bot.reply_to(message, "❌ Только для админов 5 лвл")
        return
    
    msg = bot.send_message(message.chat.id,
                          "🔍 *Статистика игрока*\n\n"
                          "Введите ID пользователя или @username:",
                          parse_mode='Markdown')
    
    bot.register_next_step_handler(msg, process_player_stats)

def process_player_stats(message):
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
    
    # Получаем статистику
    stats = db.get_user_stats(target_user)
    
    stats_text = (
        f"📊 *Статистика игрока*\n\n"
        f"👤 Имя: {stats['first_name']}\n"
        f"📱 @{stats['username'] or 'нет'}\n"
        f"🆔 ID: {stats['user_id']}\n\n"
        
        f"🏆 Уровень: {stats['level']}\n"
        f"⭐ Опыт: {stats['exp']}/{(stats['level'] + 1) * 1000}\n"
        f"💰 Деньги: {stats['money']} руб\n"
        f"🏆 Рыбопоп: {stats['fishpop']}\n\n"
        
        f"🎣 Рыбалка:\n"
        f"• Поймано рыб: {stats['total_fish']}\n"
        f"• Общий вес: {stats['total_weight']/1000:.1f} кг\n"
        f"• Обычных: {stats['stats'].get('common', 0)}\n"
        f"• Редких: {stats['stats'].get('rare', 0)}\n"
        f"• Эпических: {stats['stats'].get('epic', 0)}\n"
        f"• Легендарных: {stats['stats'].get('legendary', 0)}\n"
        f"• Мусора: {stats['stats'].get('trash', 0)}\n\n"
        
        f"⚖️ Система:\n"
        f"• Удочек: {stats['rods_count']}\n"
        f"• Предупреждений: {stats['warnings']}/2\n"
        f"• Забанен: {'✅ Да' if stats['banned'] else '❌ Нет'}\n"
        f"• Вечная удочка: {'✅ Есть' if stats['upgrades'].get('unbreakable') else '❌ Нет'}\n"
        f"• Удача: +{stats['upgrades'].get('luck_boost', 0)}%\n\n"
        
        f"📍 Текущий водоем: {WATER_BODIES[int(stats.get('location', 1))-1]['name']}\n"
    )
    
    if stats['last_fishing']:
        last_fish = datetime.fromtimestamp(stats['last_fishing']).strftime("%d.%m.%Y %H:%M")
        stats_text += f"⏰ Последняя рыбалка: {last_fish}\n"
    
    bot.reply_to(message, stats_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '📊 Логи действий')
def admin_logs_handler(message):
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 5:
        bot.reply_to(message, "❌ Только для админов 5 лвл")
        return
    
    # Последние 20 логов
    recent_logs = db.logs[-20:] if db.logs else []
    
    if not recent_logs:
        bot.reply_to(message, "📭 Логов пока нет")
        return
    
    logs_text = "📊 *Последние действия*\n\n"
    
    for log in reversed(recent_logs):
        date = datetime.fromtimestamp(log['timestamp']).strftime("%d.%m %H:%M")
        action = log['action']
        user_id = log['user_id'][:8] + "..." if len(log['user_id']) > 8 else log['user_id']
        details = log['details'][:40] + "..." if len(log['details']) > 40 else log['details']
        
        logs_text += f"📅 {date}\n"
        logs_text += f"👤 {user_id} | 📝 {action}\n"
        logs_text += f"ℹ️ {details}\n"
        
        if log.get('admin_id'):
            logs_text += f"👑 Админ: {log['admin_id']}\n"
        
        logs_text += "─" * 30 + "\n"
    
    bot.send_message(message.chat.id, logs_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '⚡ Выдать награду')
def admin_give_reward_handler(message):
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level < 5:
        bot.reply_to(message, "❌ Только для админов 5 лвл")
        return
    
    msg = bot.send_message(message.chat.id,
                          "⚡ *Выдача награды*\n\n"
                          "Введите ID пользователя или @username:",
                          parse_mode='Markdown')
    
    bot.register_next_step_handler(msg, process_reward_user)

def process_reward_user(message):
    user_input = message.text.strip()
    
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
    
    # Создаем клавиатуру с типами наград
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    btn1 = types.KeyboardButton('💰 Деньги')
    btn2 = types.KeyboardButton('🪱 Наживка')
    btn3 = types.KeyboardButton('🎣 Удочка')
    btn4 = types.KeyboardButton('🏆 Рыбопоп')
    btn5 = types.KeyboardButton('🔧 Улучшение')
    btn6 = types.KeyboardButton('⬅️ Отмена')
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    
    msg = bot.send_message(message.chat.id,
                          f"🎁 *Выдача награды*\n\n"
                          f"👤 Пользователь: {target_user}\n\n"
                          f"Выберите тип награды:",
                          parse_mode='Markdown', reply_markup=markup)
    
    bot.register_next_step_handler(msg, process_reward_type, target_user)

def process_reward_type(message, target_user_id):
    reward_type = message.text
    admin_id = message.from_user.id
    
    if reward_type == '⬅️ Отмена':
        bot.send_message(message.chat.id, "❌ Отменено",
                        reply_markup=create_admin_keyboard(5))
        return
    
    if reward_type == '💰 Деньги':
        msg = bot.send_message(message.chat.id, "💵 Введите сумму денег:")
        bot.register_next_step_handler(msg, process_money_reward, target_user_id, admin_id)
    
    elif reward_type == '🪱 Наживка':
        markup = types.InlineKeyboardMarkup(row_width=2)
        for bait in BAITS:
            if bait['price'] > 0:
                btn = types.InlineKeyboardButton(f"{bait['emoji']} {bait['name']}",
                                               callback_data=f"reward_bait_{bait['id']}_{target_user_id}_{admin_id}")
                markup.add(btn)
        
        bot.send_message(message.chat.id,
                        "🪱 Выберите наживку:",
                        reply_markup=markup)
    
    elif reward_type == '🎣 Удочка':
        markup = types.InlineKeyboardMarkup(row_width=2)
        for rod in RODS:
            if rod['price'] > 0:
                btn = types.InlineKeyboardButton(f"{rod['emoji']} {rod['name']}",
                                               callback_data=f"reward_rod_{rod['id']}_{target_user_id}_{admin_id}")
                markup.add(btn)
        
        bot.send_message(message.chat.id,
                        "🎣 Выберите удочку:",
                        reply_markup=markup)
    
    elif reward_type == '🏆 Рыбопоп':
        msg = bot.send_message(message.chat.id, "🏆 Введите количество рыбопоп:")
        bot.register_next_step_handler(msg, process_fishpop_reward, target_user_id, admin_id)
    
    elif reward_type == '🔧 Улучшение':
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn1 = types.KeyboardButton('🔧 Вечная удочка')
        btn2 = types.KeyboardButton('🍀 Удача +20%')
        btn3 = types.KeyboardButton('⬅️ Отмена')
        markup.add(btn1, btn2, btn3)
        
        msg = bot.send_message(message.chat.id,
                              "🔧 Выберите улучшение:",
                              reply_markup=markup)
        bot.register_next_step_handler(msg, process_upgrade_reward, target_user_id, admin_id)

def process_money_reward(message, target_user_id, admin_id):
    try:
        amount = int(message.text)
        if amount <= 0:
            bot.reply_to(message, "❌ Сумма должна быть положительной")
            return
        
        user_data = db.get_user(target_user_id)
        user_data['money'] += amount
        
        # Логируем
        db.add_log('admin_give_money', target_user_id, f"{amount} руб", admin_id)
        
        bot.reply_to(message,
                    f"✅ Успешно!\n\n"
                    f"💰 Пользователю {target_user_id} выдано: {amount} руб\n"
                    f"💳 Новый баланс: {user_data['money']} руб",
                    reply_markup=create_admin_keyboard(5))
    
    except ValueError:
        bot.reply_to(message, "❌ Введите число")

def process_fishpop_reward(message, target_user_id, admin_id):
    try:
        amount = int(message.text)
        if amount <= 0:
            bot.reply_to(message, "❌ Количество должно быть положительным")
            return
        
        user_data = db.get_user(target_user_id)
        user_data['fishpop'] = user_data.get('fishpop', 0) + amount
        
        # Логируем
        db.add_log('admin_give_fishpop', target_user_id, f"{amount} рыбопоп", admin_id)
        
        bot.reply_to(message,
                    f"✅ Успешно!\n\n"
                    f"🏆 Пользователю {target_user_id} выдано: {amount} рыбопоп\n"
                    f"🎯 Теперь у него: {user_data['fishpop']} рыбопоп",
                    reply_markup=create_admin_keyboard(5))
    
    except ValueError:
        bot.reply_to(message, "❌ Введите число")

@bot.callback_query_handler(func=lambda call: call.data.startswith('reward_bait_'))
def handle_reward_bait(call):
    data = call.data.split('_')
    bait_id = data[2]
    target_user_id = data[3]
    admin_id = data[4]
    
    bait_info = next((b for b in BAITS if str(b['id']) == bait_id), None)
    if not bait_info:
        bot.answer_callback_query(call.id, "❌ Наживка не найдена")
        return
    
    # Выдаем наживку
    new_count = db.add_bait(target_user_id, bait_id, 1)
    
    # Логируем
    db.add_log('admin_give_bait', target_user_id, bait_info['name'], admin_id)
    
    response = (
        f"✅ Успешно!\n\n"
        f"🪱 Пользователю {target_user_id} выдано: {bait_info['name']}\n"
        f"📦 Теперь у него: {new_count} шт"
    )
    
    try:
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id,
                            parse_mode='Markdown')
    except:
        bot.send_message(call.message.chat.id, response, parse_mode='Markdown')
    
    bot.answer_callback_query(call.id, "✅ Выдано!")

@bot.callback_query_handler(func=lambda call: call.data.startswith('reward_rod_'))
def handle_reward_rod(call):
    data = call.data.split('_')
    rod_id = data[2]
    target_user_id = data[3]
    admin_id = data[4]
    
    rod_info = next((r for r in RODS if str(r['id']) == rod_id), None)
    if not rod_info:
        bot.answer_callback_query(call.id, "❌ Удочка не найдена")
        return
    
    # Выдаем удочку
    db.add_rod(target_user_id, rod_id)
    
    # Логируем
    db.add_log('admin_give_rod', target_user_id, rod_info['name'], admin_id)
    
    response = (
        f"✅ Успешно!\n\n"
        f"🎣 Пользователю {target_user_id} выдано: {rod_info['name']}\n"
        f"🔧 Прочность: {rod_info['durability']}\n"
        f"🍀 Удача: +{rod_info['luck']}%"
    )
    
    try:
        bot.edit_message_text(response, call.message.chat.id, call.message.message_id,
                            parse_mode='Markdown')
    except:
        bot.send_message(call.message.chat.id, response, parse_mode='Markdown')
    
    bot.answer_callback_query(call.id, "✅ Выдано!")

def process_upgrade_reward(message, target_user_id, admin_id):
    upgrade_type = message.text
    
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
    
    # Логируем
    db.add_log('admin_give_upgrade', target_user_id, upgrade_text, admin_id)
    
    bot.reply_to(message,
                f"✅ Успешно!\n\n"
                f"🔧 Пользователю {target_user_id} выдано: {upgrade_text}\n"
                f"🎯 Теперь улучшения: {user_data['upgrades']}",
                reply_markup=create_admin_keyboard(5))

# ========== ЕЖЕДНЕВНЫЕ ЗАДАНИЯ ==========
@bot.message_handler(func=lambda msg: msg.text == '🎯 Ежедневное задание')
def daily_task_handler(message):
    user = message.from_user
    user_id_str = str(user.id)
    
    if db.is_banned(user_id_str):
        return
    
    user_data = db.get_user(user.id)
    
    if user_data.get('daily_task'):
        task = user_data['daily_task']
        progress = user_data.get('daily_progress', {})
        
        task_text = f"📅 *Текущее задание:*\n\n🎯 {task['question']}\n🏆 Награда: {task['reward']} руб\n\n"
        
        if task['type'] == 'catch_count':
            current = progress.get('count', 0)
            task_text += f"📊 Прогресс: {current}/{task['target']} рыб\n"
        
        elif task['type'] == 'weight':
            current = progress.get('weight', 0)
            task_text += f"📊 Прогресс: {current/1000:.1f}/{task['target']/1000:.1f} кг\n"
        
        elif task['type'] == 'money':
            # Для денег прогресс не показываем
            pass
        
        elif task['type'] == 'rarity':
            task_text += f"📊 Нужно поймать: {task['target']} рыбу\n"
        
        elif task['type'] == 'bait_variety':
            current = progress.get('variety', 0)
            task_text += f"📊 Прогресс: {current}/{task['target']} наживок\n"
        
        elif task['type'] == 'locations':
            current = progress.get('locations', 0)
            task_text += f"📊 Прогресс: {current}/{task['target']} водоемов\n"
        
        # Проверяем время
        last_daily = user_data.get('last_daily')
        if last_daily:
            next_daily = last_daily + 86400
            current_time = time.time()
            if current_time < next_daily:
                hours_left = int((next_daily - current_time) // 3600)
                minutes_left = int(((next_daily - current_time) % 3600) // 60)
                task_text += f"\n⏳ Следующее задание через: {hours_left}ч {minutes_left}м\n"
        
        bot.send_message(message.chat.id, task_text, parse_mode='Markdown')
        
    else:
        # Выдаем новое задание
        if db.assign_daily_task(user.id):
            # Сообщение уже отправлено в функции
            pass
        else:
            bot.send_message(message.chat.id,
                           "⏳ Вы уже получали задание сегодня!\n"
                           "Приходите завтра за новым заданием.",
                           parse_mode='Markdown')

# ========== ОБРАБОТКА КНОПОК ==========
@bot.message_handler(func=lambda msg: msg.text == '🎣 Начать рыбалку')
def fishing_button_handler(message):
    fishing_command_handler(message)

@bot.message_handler(func=lambda msg: msg.text == '🎣 Забросить удочку')
def fishing_cast_handler(message):
    fishing_command_handler(message)

@bot.message_handler(func=lambda msg: msg.text == '📍 Сменить водоем')
def location_button_handler(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    current_id = int(user_data.get('location', 1)) - 1
    
    locations_text = f"📍 *Текущий водоем:* {WATER_BODIES[current_id]['emoji']} {WATER_BODIES[current_id]['name']}\n\n"
    locations_text += "*Выберите новый водоем:*\n\n"
    
    for i, loc in enumerate(WATER_BODIES):
        price_text = f" | 💰 Вход: {loc['price_entry']} руб" if loc['price_entry'] > 0 else ""
        locations_text += f"{loc['emoji']} *{loc['name']}*\n📌 {loc['region']}{price_text}\n\n"
    
    bot.send_message(message.chat.id, locations_text, parse_mode='Markdown',
                    reply_markup=create_location_keyboard())

@bot.message_handler(func=lambda msg: any(msg.text == f"{loc['emoji']} {loc['name']}" for loc in WATER_BODIES))
def select_location_handler(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    for loc in WATER_BODIES:
        if message.text == f"{loc['emoji']} {loc['name']}":
            # Проверяем достаточно ли денег
            if user_data['money'] < loc['price_entry']:
                bot.send_message(message.chat.id,
                               f"❌ Недостаточно денег!\n"
                               f"Нужно: {loc['price_entry']} руб\n"
                               f"У вас: {user_data['money']} руб")
                return
            
            # Списание денег
            if loc['price_entry'] > 0:
                user_data['money'] -= loc['price_entry']
            
            user_data['location'] = str(loc['id'])
            db.save_data()
            
            bot.send_message(message.chat.id,
                           f"✅ *Водоем изменен!*\n\n"
                           f"{loc['emoji']} *{loc['name']}*\n"
                           f"📌 {loc['region']}\n"
                           f"🌊 {loc['depth']}\n\n"
                           f"Теперь вы можете ловить рыбу здесь!",
                           parse_mode='Markdown',
                           reply_markup=create_main_keyboard())
            return

@bot.message_handler(func=lambda msg: msg.text == '📊 Статистика')
def stats_button_handler(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    stats_text = (
        f"📊 *Ваша статистика*\n\n"
        f"👤 Игрок: {user.first_name}\n"
        f"🏆 Уровень: {user_data.get('level', 1)}\n"
        f"⭐ Опыт: {user_data.get('exp', 0)}/{(user_data.get('level', 1) + 1) * 1000}\n"
        f"💰 Деньги: {user_data['money']} руб\n"
        f"🏆 Рыбопоп: {user_data.get('fishpop', 0)}\n\n"
        
        f"🎣 Рыбалка:\n"
        f"• Всего рыб: {user_data['total_fish']}\n"
        f"• Общий вес: {user_data['total_weight']/1000:.1f} кг\n"
        f"• Обычных: {user_data['stats']['common']}\n"
        f"• Редких: {user_data['stats']['rare']}\n"
        f"• Эпических: {user_data['stats']['epic']}\n"
        f"• Легендарных: {user_data['stats']['legendary']}\n"
        f"• Мусора: {user_data['stats']['trash']}\n\n"
        
        f"🔧 Улучшения:\n"
        f"• Вечная удочка: {'✅ Да' if user_data['upgrades']['unbreakable'] else '❌ Нет'}\n"
        f"• Удача: +{user_data['upgrades']['luck_boost']}%\n\n"
        
        f"⚠️ Предупреждений: {db.get_warning_count(user.id)}/2\n"
    )
    
    bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '🎒 Инвентарь')
def inventory_button_handler(message):
    user = message.from_user
    user_data = db.get_user(user.id)
    
    # Удочки
    inventory_text = f"🎒 *Инвентарь {user.first_name}*\n\n"
    inventory_text += "🎣 *Удочки:*\n"
    
    for rod_id in user_data.get('rods', ['1']):
        rod_info = next((r for r in RODS if str(r['id']) == rod_id), None)
        if rod_info:
            durability = user_data['rod_durability'].get(rod_id, rod_info['durability'])
            active = " ✅" if rod_id == user_data.get('active_rod', '1') else ""
            inventory_text += f"{rod_info['emoji']} {rod_info['name']}: {durability}/{rod_info['durability']}{active}\n"
    
    # Наживка
    inventory_text += "\n🪱 *Наживка:*\n"
    for bait in BAITS:
        count = user_data['baits'].get(str(bait['id']), 0)
        if count > 0:
            inventory_text += f"{bait['emoji']} {bait['name']}: {count} шт\n"
    
    # Последние уловы
    inventory_text += "\n🐟 *Последние уловы:*\n"
    if user_data['fish_caught']:
        for catch in user_data['fish_caught'][-5:]:
            inventory_text += f"{catch['emoji']} {catch['name']} ({catch['weight']}г) - {catch['value']} руб\n"
    else:
        inventory_text += "Пока пусто\n"
    
    bot.send_message(message.chat.id, inventory_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '🏆 Топ игроков')
def top_button_handler(message):
    top_command(message)

@bot.message_handler(func=lambda msg: msg.text == '📰 Новости')
def news_button_handler(message):
    news_list = db.get_news(5)
    
    if not news_list:
        news_text = "📰 *Новости*\n\nПока нет новостей"
    else:
        news_text = "📰 *Последние новости*\n\n"
        for news in news_list:
            date = datetime.fromtimestamp(news['timestamp']).strftime("%d.%m.%Y %H:%M")
            news_text += f"📅 {date}\n{news['text']}\n\n{'─'*30}\n\n"
    
    bot.send_message(message.chat.id, news_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '❓ Помощь')
def help_button_handler(message):
    help_text = (
        "🎣 *Помощь по игре*\n\n"
        "📋 *Основные команды:*\n"
        "/start - Начать игру\n"
        "/stats - Статистика\n"
        "/top - Топ игроков\n"
        "/news - Новости (админы 5 лвл)\n\n"
        
        "🎮 *Как играть:*\n"
        "1. Выберите водоем (10 вариантов)\n"
        "2. Купите наживку в магазине\n"
        "3. Выберите удочку\n"
        "4. Начните рыбалку\n\n"
        
        "🪱 *Наживка:*\n"
        "• Разная наживка приманивает разную рыбу\n"
        "• Обычный червяк выдается бесплатно\n"
        "• Дорогая наживка увеличивает удачу\n\n"
        
        "🎣 *Удочки:*\n"
        "• У каждой удочки своя прочность\n"
        "• Удочки ломаются от тяжелой рыбы\n"
        "• Ремонтируйте удочки в магазине\n"
        "• Можно купить улучшение 'вечная удочка'\n\n"
        
        "💰 *Донат:*\n"
        "• Поддержите проект для получения бонусов\n"
        "• Улучшения, рыбопоп, специальные удочки\n"
        "• Карта Тинькофф: `2200702034105283`\n\n"
        
        "📢 *Новости:*\n"
        "• Админы публикуют новости об обновлениях\n"
        "• Ежедневные задания с наградами\n"
        "• Следите за обновлениями!\n\n"
        
        "🎯 *Ежедневные задания:*\n"
        "• Каждый день новое задание\n"
        "• Выполняйте для получения наград\n"
        "• Задания обновляются раз в 24 часа\n\n"
        
        "Удачи на рыбалке! 🎣"
    )
    
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(func=lambda msg: msg.text == '⬅️ Назад')
def back_button_handler(message):
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
    user = message.from_user
    user_id_str = str(user.id)
    
    admin_level = ADMINS.get(user_id_str, 0)
    if admin_level > 0:
        bot.send_message(message.chat.id, "👑 Админ панель",
                        reply_markup=create_admin_keyboard(admin_level))
    else:
        bot.send_message(message.chat.id, "📋 Главное меню",
                        reply_markup=create_main_keyboard())

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
    return "🎣 Fishing Bot Complete Edition is running!", 200

@app.route('/set_webhook', methods=['GET'])
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

@app.route('/remove_webhook', methods=['GET'])
def remove_webhook():
    try:
        bot.remove_webhook()
        return "✅ Webhook удален", 200
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
            "news": len(db.news),
            "transactions": len([t for t in db.transactions if t['status'] == 'pending']),
            "timestamp": datetime.now().isoformat()
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)}), 500

# ========== ОБРАБОТКА ВСЕХ СООБЩЕНИЙ ==========
@bot.message_handler(func=lambda message: True, content_types=['text'])
def handle_all_messages(message):
    delete_links_in_group(message)
    
    text = message.text
    # Игнорируем уже обработанные команды
    if text in ['🎣 Начать рыбалку', '📍 Сменить водоем', '🛒 Магазин', '📊 Статистика',
                '🎒 Инвентарь', '🏆 Топ игроков', '📰 Новости', '💰 Донат', '❓ Помощь',
                '🎯 Ежедневное задание', '🎣 Забросить удочку', '📋 Меню', '⬅️ Назад',
                '⬅️ В меню', '👑 Админ панель', '📋 Список игроков', '⚡ Выдать награду',
                '⚠️ Выдать предупреждение', '🚫 Забанить', '✅ Снять бан', '📢 Отправить новость',
                '📊 Логи действий', '🔍 Статистика игрока', '🔄 Сбросить прогресс']:
        return
    if text and text.startswith('/'):
        return

@bot.message_handler(content_types=['photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle_media_messages(message):
    delete_links_in_group(message)

# ========== ЗАПУСК ==========
if __name__ == '__main__':
    print("=" * 50)
    print("🎣 Fishing Bot Complete Edition")
    print(f"✅ Webhook URL: {WEBHOOK_URL if WEBHOOK_URL else 'Не настроен'}")
    print("=" * 50)
    
    try:
        bot_info = bot.get_me()
        print(f"✅ Бот загружен: @{bot_info.username}")
    except Exception as e:
        print(f"❌ Ошибка загрузки бота: {e}")
    
    # Keep-alive
    if RENDER_URL:
        keeper = KeepAliveService(RENDER_URL)
        keeper.start()
        print("✅ Keep-alive service started")
    
    # Запуск Flask
    port = int(os.environ.get('PORT', 10000))
    print(f"🌐 Запуск Flask на порту {port}...")
    app.run(host='0.0.0.0', port=port, debug=False)
