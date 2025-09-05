import sqlite3
import json
import logging

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
db_logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_name='learning_bot.db'):
        self.db_name = db_name
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_tables()

    def _connect(self):
        try:
            self.conn = sqlite3.connect(self.db_name)
            self.cursor = self.conn.cursor()
            db_logger.info(f"Connected to database: {self.db_name}")
        except sqlite3.Error as e:
            db_logger.error(f"Error connecting to database: {e}")
            raise

    def _create_tables(self):
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS vocabulary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    subject TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    lesson TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    item_data TEXT NOT NULL,
                    search_key TEXT NOT NULL,
                    UNIQUE(subject, grade, lesson, content_type, search_key)
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_sessions (
                    user_id INTEGER PRIMARY KEY,
                    session_data TEXT NOT NULL
                )
            ''')
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_progress (
                    user_id INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    grade TEXT NOT NULL,
                    lesson TEXT NOT NULL,
                    content_type TEXT NOT NULL,
                    learned_indices TEXT NOT NULL,
                    PRIMARY KEY (user_id, subject, grade, lesson, content_type)
                )
            ''')
            self.conn.commit()
            db_logger.info("Tables checked/created successfully.")
        except sqlite3.Error as e:
            db_logger.error(f"Error creating tables: {e}")
            raise

    # ✅ تابع حذف شده به اینجا بازگردانده شد
    def insert_vocabulary_item(self, subject, grade, lesson, content_type, item_data):
        """
        یک آیتم درسی را به جدول vocabulary اضافه می‌کند.
        """
        try:
            search_key = item_data.get('arabic') or item_data.get('english') or item_data.get('word')
            item_json = json.dumps(item_data, ensure_ascii=False)
            self.cursor.execute('''
                INSERT OR IGNORE INTO vocabulary (subject, grade, lesson, content_type, item_data, search_key)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (subject, grade, lesson, content_type, item_json, search_key))
            self.conn.commit()
            if self.cursor.rowcount == 0:
                db_logger.debug(f"Duplicate entry ignored for: {search_key} in {subject}/{grade}/{lesson}")
                return False
            db_logger.debug(f"Inserted: {search_key} into {subject}/{grade}/{lesson}")
            return True
        except sqlite3.Error as e:
            db_logger.error(f"Error inserting vocabulary item: {e}")
            return False

    def get_vocabulary_by_lesson(self, subject, grade, lesson, content_type):
        try:
            self.cursor.execute('''
                SELECT item_data FROM vocabulary
                WHERE subject = ? AND grade = ? AND lesson = ? AND content_type = ?
            ''', (subject, grade, lesson, content_type))
            rows = self.cursor.fetchall()
            return [json.loads(row[0]) for row in rows]
        except sqlite3.Error as e:
            db_logger.error(f"Error getting vocabulary for {subject}/{grade}/{lesson}: {e}")
            return []

    def save_user_progress(self, user_id, subject, grade, lesson, content_type, learned_indices):
        try:
            indices_json = json.dumps(list(learned_indices))
            self.cursor.execute('''
                INSERT OR REPLACE INTO user_progress (user_id, subject, grade, lesson, content_type, learned_indices)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, subject, grade, lesson, content_type, indices_json))
            self.conn.commit()
        except sqlite3.Error as e:
            db_logger.error(f"Error saving user progress: {e}")

    def load_user_progress(self, user_id, subject, grade, lesson, content_type):
        try:
            self.cursor.execute('''
                SELECT learned_indices FROM user_progress
                WHERE user_id = ? AND subject = ? AND grade = ? AND lesson = ? AND content_type = ?
            ''', (user_id, subject, grade, lesson, content_type))
            row = self.cursor.fetchone()
            if row:
                return set(json.loads(row[0]))
            return set()
        except sqlite3.Error as e:
            db_logger.error(f"Error loading user progress: {e}")
            return set()

    def save_user_session(self, user_id, session_data):
        try:
            session_json = json.dumps(session_data, ensure_ascii=False)
            self.cursor.execute('INSERT OR REPLACE INTO user_sessions (user_id, session_data) VALUES (?, ?)',
                                (user_id, session_json))
            self.conn.commit()
        except sqlite3.Error as e:
            db_logger.error(f"Error saving user session for {user_id}: {e}")

    def load_user_session(self, user_id):
        try:
            self.cursor.execute('SELECT session_data FROM user_sessions WHERE user_id = ?', (user_id,))
            row = self.cursor.fetchone()
            return json.loads(row[0]) if row else {}
        except (sqlite3.Error, json.JSONDecodeError) as e:
            db_logger.error(f"Error loading user session for {user_id}: {e}")
            return {}

    def close(self):
        if self.conn:
            self.conn.close()
            db_logger.info("Database connection closed.")