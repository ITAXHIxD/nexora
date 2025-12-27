import sqlite3, threading, logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.db_path = 'bot_data.db'
        self.lock = threading.Lock()
        if self.enabled:
            self.init_database()
    def init_database(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS personalities (
                        channel_id TEXT PRIMARY KEY,
                        personality TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS message_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        channel_id TEXT NOT NULL,
                        author TEXT NOT NULL,
                        content TEXT NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bot_stats (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        stat_name TEXT NOT NULL,
                        stat_value INTEGER NOT NULL,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                conn.commit()
                logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            self.enabled = False

    def save_personality(self, channel_id: str, personality: str):
        if not self.enabled: return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO personalities (channel_id, personality, updated_at)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                ''', (channel_id, personality))
                conn.commit()
        except Exception as e:
            logger.error(f"Error saving personality: {e}")

    def load_personalities(self) -> Dict[str, str]:
        if not self.enabled: return {}
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT channel_id, personality FROM personalities')
                return dict(cursor.fetchall())
        except Exception as e:
            logger.error(f"Error loading personalities: {e}")
            return {}

    def delete_personality(self, channel_id: str):
        if not self.enabled: return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM personalities WHERE channel_id = ?', (channel_id,))
                conn.commit()
        except Exception as e:
            logger.error(f"Error deleting personality: {e}")

    def add_message(self, channel_id: str, author: str, content: str):
        if not self.enabled: return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO message_history (channel_id, author, content)
                    VALUES (?, ?, ?)
                ''', (channel_id, author, content[:500]))
                conn.commit()
                cursor.execute('''
                    DELETE FROM message_history 
                    WHERE channel_id = ? AND author = ? AND id NOT IN (
                        SELECT id FROM message_history 
                        WHERE channel_id = ? AND author = ?
                        ORDER BY timestamp DESC 
                        LIMIT 20
                    )
                ''', (channel_id, author, channel_id, author))
                conn.commit()
        except Exception as e:
            logger.error(f"Error adding message: {e}")

    def get_recent_messages(self, channel_id: str, author: str = None, limit: int = 10) -> List[Dict]:
        if not self.enabled: return []
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                if author:
                    cursor.execute('''
                        SELECT author, content, timestamp FROM message_history
                        WHERE channel_id = ? AND author = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ''', (channel_id, author, limit))
                else:
                    cursor.execute('''
                        SELECT author, content, timestamp FROM message_history
                        WHERE channel_id = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    ''', (channel_id, limit))
                rows = cursor.fetchall()
                messages = [{'author': a, 'content': c, 'timestamp': t} for (a, c, t) in rows]
                return list(reversed(messages))
        except Exception as e:
            logger.error(f"Error getting recent messages: {e}")
            return []
