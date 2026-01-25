# database_models.py
from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, JSON, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from datetime import datetime
import os

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(String, primary_key=True)  # Telegram user_id
    username = Column(String, nullable=True)
    first_name = Column(String)
    
    # Основные данные
    worms = Column(Integer, default=10)
    coins = Column(Integer, default=100)
    fishing_level = Column(Integer, default=1)
    experience = Column(Integer, default=0)
    total_fish = Column(Integer, default=0)
    total_coins_earned = Column(Integer, default=0)
    
    # Статистика
    common_fish = Column(Integer, default=0)
    rare_fish = Column(Integer, default=0)
    epic_fish = Column(Integer, default=0)
    legendary_fish = Column(Integer, default=0)
    trash_fish = Column(Integer, default=0)
    
    # Текущие настройки
    current_location = Column(String, default='Волга')
    current_rod = Column(String, default='🎣 Маховая удочка')
    current_bait = Column(String, default='🌱 Обычный червь')
    
    # Ник для топа и настройки
    top_nickname = Column(String, nullable=True)
    hide_from_top = Column(Boolean, default=False)
    
    # Время
    last_fishing_time = Column(DateTime, nullable=True)
    last_worm_refill = Column(DateTime, default=datetime.now)
    last_daily_reset = Column(DateTime, default=datetime.now)
    registered_at = Column(DateTime, default=datetime.now)
    
    # Донат и улучшения
    luck_bonus = Column(Float, default=0.0)
    unbreakable_rods = Column(Boolean, default=False)
    
    # Инвентарь (храним как JSON)
    inventory = Column(JSON, default={
        'rods': [{"name": "🎣 Маховая удочка", "equipped": True, "durability": 100, "max_durability": 100, "upgrades": [], "unbreakable": False}],
        'baits': [{"name": "🌱 Обычный червь", "count": 10}],
        'fish': {}
    })
    
    # Ежедневные задания
    daily_quests = Column(JSON, default={})
    quests_completed_today = Column(Integer, default=0)
    
    # Баны и предупреждения
    warnings = Column(JSON, default=[])
    banned_until = Column(DateTime, nullable=True)
    muted_until = Column(DateTime, nullable=True)
    
    # История доната
    donate_history = Column(JSON, default=[])
    
    # Избранные места
    favorite_fishing_spots = Column(JSON, default=[])
    achievements = Column(JSON, default=[])

class AdminLog(Base):
    __tablename__ = 'admin_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    admin_id = Column(String)
    action = Column(String)
    target_id = Column(String, nullable=True)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.now)

class ActionLog(Base):
    __tablename__ = 'action_logs'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    action_type = Column(String)
    details = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.now)

class News(Base):
    __tablename__ = 'news'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String)
    content = Column(Text)
    author_id = Column(String)
    timestamp = Column(DateTime, default=datetime.now)

class DonateTransaction(Base):
    __tablename__ = 'donate_transactions'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    package_name = Column(String)
    amount = Column(Float)
    transaction_id = Column(String)
    processed = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.now)

class SupportTicket(Base):
    __tablename__ = 'support_tickets'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String)
    category = Column(String, default='Общий')
    message = Column(Text)
    status = Column(String, default='open')  # open, answered, closed
    admin_id = Column(String, nullable=True)
    reply = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)

# Настройка соединения с БД
def get_database_url():
    """Получить URL базы данных из окружения или использовать SQLite для разработки"""
    if 'DATABASE_URL' in os.environ:
        # Для Render PostgreSQL
        return os.environ['DATABASE_URL'].replace('postgres://', 'postgresql://')
    else:
        # Для локальной разработки
        return 'sqlite:///bot_database.db'

engine = create_engine(get_database_url())
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Создание таблиц
def init_db():
    Base.metadata.create_all(bind=engine)
    print("✅ База данных инициализирована")

# Получение сессии
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
