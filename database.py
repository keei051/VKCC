import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Абсолютный путь к файлу базы данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "links.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

async def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            long_url TEXT NOT NULL,
            short_url TEXT NOT NULL,
            title TEXT DEFAULT 'Без названия',
            vk_key TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, long_url)
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"✅ БД инициализирована: {DB_PATH}")

async def save_link(user_id: int, long_url: str, short_url: str, title: str, vk_key: str) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO links (user_id, long_url, short_url, title, vk_key)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, long_url, short_url, title, vk_key))
        conn.commit()
        conn.close()
        logger.info(f"✅ Ссылка сохранена: {short_url} ({title}) для user_id={user_id}")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"⚠️ Попытка сохранить дубликат: {long_url} для user_id={user_id}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении ссылки: {e}")
        return False

async def get_links_by_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, short_url, created_at
        FROM links
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    results = cursor.fetchall()
    conn.close()
    return [tuple(row) for row in results]

async def get_link_by_id(link_id: int, user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, long_url, short_url, title, vk_key, created_at
        FROM links
        WHERE id = ? AND user_id = ?
    """, (link_id, user_id))
    result = cursor.fetchone()
    conn.close()
    return tuple(result) if result else None

async def delete_link(link_id: int, user_id: int) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM links WHERE id = ? AND user_id = ?", (link_id, user_id))
        conn.commit()
        conn.close()
        logger.info(f"🗑 Ссылка с id={link_id} удалена для user_id={user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при удалении ссылки: {e}")
        return False

async def rename_link(link_id: int, user_id: int, new_title: str) -> bool:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE links SET title = ? WHERE id = ? AND user_id = ?
        """, (new_title, link_id, user_id))
        conn.commit()
        conn.close()
        logger.info(f"✏️ Ссылка id={link_id} переименована в '{new_title}' для user_id={user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка при переименовании ссылки: {e}")
        return False
