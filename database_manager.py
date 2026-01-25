# database_manager.py
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import time
import json
from database_models import User, AdminLog, ActionLog, News, DonateTransaction, SupportTicket, get_db

class DatabaseManager:
    def __init__(self):
        self.SessionLocal = get_db
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        from database_models import init_db
        init_db()
        print("✅ Менеджер базы данных инициализирован")
    
    def get_user(self, user_id: str, db: Session = None):
        """Получить пользователя из базы данных"""
        close_db = False
        if db is None:
            db = next(self.SessionLocal())
            close_db = True
        
        try:
            user = db.query(User).filter(User.id == str(user_id)).first()
            
            if not user:
                # Создаем нового пользователя
                user = User(
                    id=str(user_id),
                    first_name="Игрок",
                    last_worm_refill=datetime.now(),
                    last_daily_reset=datetime.now(),
                    registered_at=datetime.now()
                )
                db.add(user)
                db.commit()
                print(f"👤 Создан новый пользователь: {user_id}")
            
            # Автопополнение червей
            current_time = datetime.now()
            time_passed = current_time - user.last_worm_refill
            worms_to_add = int(time_passed.total_seconds() // 900)  # 15 минут
            
            if worms_to_add > 0:
                user.worms = min(user.worms + worms_to_add, 10)
                user.last_worm_refill = current_time
                db.commit()
            
            # Сброс ежедневных заданий
            if current_time.date() > user.last_daily_reset.date():
                user.daily_quests = {}
                user.quests_completed_today = 0
                user.last_daily_reset = current_time
                db.commit()
            
            return user
            
        finally:
            if close_db:
                db.close()
    
    def update_user(self, user: User, db: Session = None):
        """Обновить пользователя в базе данных"""
        close_db = False
        if db is None:
            db = next(self.SessionLocal())
            close_db = True
        
        try:
            db.merge(user)
            db.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка обновления пользователя {user.id}: {e}")
            db.rollback()
            return False
        finally:
            if close_db:
                db.close()
    
    def add_fish(self, user_id: str, fish_data: dict):
        """Добавить пойманную рыбу"""
        db = next(self.SessionLocal())
        try:
            user = self.get_user(user_id, db)
            
            # Обновляем общее количество
            user.total_fish += 1
            
            # Обновляем статистику по редкостям
            rarity = fish_data.get('rarity', 'обычная')
            if rarity == 'обычная':
                user.common_fish += 1
            elif rarity == 'редкая':
                user.rare_fish += 1
                user.experience += 30
            elif rarity == 'эпическая':
                user.epic_fish += 1
                user.experience += 100
            elif rarity == 'легендарная':
                user.legendary_fish += 1
                user.experience += 500
            elif rarity == 'мусор':
                user.trash_fish += 1
                user.experience += 1
            
            # Добавляем в инвентарь
            fish_name = fish_data['name']
            inventory = user.inventory
            
            if 'fish' not in inventory:
                inventory['fish'] = {}
            
            if fish_name in inventory['fish']:
                inventory['fish'][fish_name] += 1
            else:
              inventory['fish'][fish_name] = 1
            
            user.inventory = inventory
            user.last_fishing_time = datetime.now()
            
            # Проверяем уровень
            while user.experience >= user.fishing_level * 100:
                user.experience -= user.fishing_level * 100
                user.fishing_level += 1
            
            db.commit()
            print(f"✅ Рыба добавлена пользователю {user_id}: {fish_name}")
            return True
            
        except Exception as e:
            print(f"❌ Ошибка добавления рыбы: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def add_coins(self, user_id: str, amount: int):
        """Добавить монеты пользователю"""
        db = next(self.SessionLocal())
        try:
            user = self.get_user(user_id, db)
            user.coins += amount
            user.total_coins_earned += amount
            db.commit()
            print(f"💰 Добавлено {amount} монет пользователю {user_id}")
            return user.coins
        except Exception as e:
            print(f"❌ Ошибка добавления монет: {e}")
            db.rollback()
            return 0
        finally:
            db.close()
    
    def log_admin_action(self, admin_id: str, action: str, target_id: str = None, details: str = ""):
        """Логировать действие админа"""
        db = next(self.SessionLocal())
        try:
            log = AdminLog(
                admin_id=str(admin_id),
                action=action,
                target_id=str(target_id) if target_id else None,
                details=details,
                timestamp=datetime.now()
            )
            db.add(log)
            db.commit()
            print(f"📝 Лог админа: {admin_id} -> {action}")
            return True
        except Exception as e:
            print(f"❌ Ошибка логирования админа: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def log_action(self, user_id: str, action_type: str, details: str = ""):
        """Логировать действие пользователя"""
        db = next(self.SessionLocal())
        try:
            log = ActionLog(
                user_id=str(user_id),
                action_type=action_type,
                details=details,
                timestamp=datetime.now()
            )
            db.add(log)
            db.commit()
            return True
        except Exception as e:
            print(f"❌ Ошибка логирования действия: {e}")
            db.rollback()
            return False
        finally:
            db.close()
    
    def get_top_players(self, category: str = "coins", limit: int = 10):
        """Получить топ игроков"""
        db = next(self.SessionLocal())
        try:
            if category == "coins":
                users = db.query(User).filter(User.hide_from_top == False)\
                    .order_by(User.total_coins_earned.desc())\
                    .limit(limit).all()
            elif category == "level":
                users = db.query(User).filter(User.hide_from_top == False)\
                    .order_by(User.fishing_level.desc(), User.experience.desc())\
                    .limit(limit).all()
            elif category == "fish":
                users = db.query(User).filter(User.hide_from_top == False)\
                    .order_by(User.total_fish.desc())\
                    .limit(limit).all()
            elif category == "rare":
                # Считаем очки: легендарные*100 + эпические*10 + редкие
                users = db.query(User).filter(User.hide_from_top == False).all()
                users.sort(key=lambda u: u.legendary_fish*100 + u.epic_fish*10 + u.rare_fish, reverse=True)
                users = users[:limit]
            
            result = []
            for user in users:
                display_name = user.top_nickname or user.first_name
                
                if category == "coins":score = user.total_coins_earned
                elif category == "level":
                    score = user.fishing_level
                elif category == "fish":
                    score = user.total_fish
                elif category == "rare":
                    score = user.legendary_fish*100 + u.epic_fish*10 + u.rare_fish
                
                result.append({
                    'user_id': user.id,
                    'username': user.username,
                    'display_name': display_name,
                    'score': score,
                    'level': user.fishing_level
                })
            
            return result
            
        except Exception as e:
            print(f"❌ Ошибка получения топа: {e}")
            return []
        finally:
            db.close()
    
    def create_support_ticket(self, user_id: str, message: str, category: str = "Общий"):
        """Создать тикет поддержки"""
        db = next(self.SessionLocal())
        try:
            # Находим максимальный ID
            max_id = db.query(SupportTicket).order_by(SupportTicket.id.desc()).first()
            ticket_id = (max_id.id + 1) if max_id else 1
            
            ticket = SupportTicket(
                id=ticket_id,
                user_id=str(user_id),
                category=category,
                message=message,
                status='open',
                created_at=datetime.now()
            )
            
            db.add(ticket)
            db.commit()
            
            print(f"🆘 Создан тикет #{ticket_id} от пользователя {user_id}")
            return ticket
            
        except Exception as e:
            print(f"❌ Ошибка создания тикета: {e}")
            db.rollback()
            return None
        finally:
            db.close()
    
    def get_all_users_count(self):
        """Получить количество всех пользователей"""
        db = next(self.SessionLocal())
        try:
            return db.query(User).count()
        except:
            return 0
        finally:
            db.close()

# Создаем глобальный экземпляр
db_manager = DatabaseManager()
