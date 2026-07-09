import sqlite3
from datetime import datetime, timedelta
from typing import List, Tuple, Optional

class Database:
    def __init__(self, db_path='subscriptions.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Создание таблиц"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Таблица подписок
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    cost REAL NOT NULL,
                    renewal_date TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    notified INTEGER DEFAULT 0
                )
            ''')
            
            # Таблица уведомлений
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    subscription_id INTEGER NOT NULL,
                    days_before INTEGER NOT NULL,
                    sent INTEGER DEFAULT 0,
                    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
                )
            ''')
            
            conn.commit()

    def add_subscription(self, user_id: int, name: str, cost: float, renewal_date: str) -> int:
        """Добавление подписки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO subscriptions (user_id, name, cost, renewal_date)
                VALUES (?, ?, ?, ?)
            ''', (user_id, name, cost, renewal_date))
            conn.commit()
            return cursor.lastrowid

    def get_subscriptions(self, user_id: int) -> List[Tuple]:
        """Получение всех подписок пользователя"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, name, cost, renewal_date
                FROM subscriptions
                WHERE user_id = ?
                ORDER BY renewal_date
            ''', (user_id,))
            return cursor.fetchall()

    def get_subscription(self, sub_id: int) -> Optional[Tuple]:
        """Получение подписки по ID"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, name, cost, renewal_date
                FROM subscriptions
                WHERE id = ?
            ''', (sub_id,))
            return cursor.fetchone()

    def delete_subscription(self, sub_id: int) -> bool:
        """Удаление подписки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM subscriptions WHERE id = ?', (sub_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_subscription(self, sub_id: int, name: str, cost: float, renewal_date: str) -> bool:
        """Обновление подписки"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE subscriptions
                SET name = ?, cost = ?, renewal_date = ?
                WHERE id = ?
            ''', (name, cost, renewal_date, sub_id))
            conn.commit()
            return cursor.rowcount > 0

    def get_total_cost(self, user_id: int) -> float:
        """Общая стоимость всех подписок"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT SUM(cost) FROM subscriptions WHERE user_id = ?
            ''', (user_id,))
            result = cursor.fetchone()[0]
            return result if result else 0.0

    def get_due_soon(self, user_id: int, days: int = 7) -> List[Tuple]:
        """Подписки, которые истекают в ближайшие N дней"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            future = (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')
            cursor.execute('''
                SELECT id, name, cost, renewal_date
                FROM subscriptions
                WHERE user_id = ?
                AND renewal_date BETWEEN ? AND ?
                AND notified = 0
                ORDER BY renewal_date
            ''', (user_id, today, future))
            return cursor.fetchall()

    def get_all_active_subs(self) -> List[Tuple]:
        """Все подписки (для восстановления напоминаний при запуске)"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, user_id, name, cost, renewal_date
                FROM subscriptions
                ORDER BY renewal_date
            ''')
            return cursor.fetchall()

    def mark_notified(self, sub_id: int):
        """Отметить подписку как уведомлённую"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE subscriptions SET notified = 1 WHERE id = ?
            ''', (sub_id,))
            conn.commit()
