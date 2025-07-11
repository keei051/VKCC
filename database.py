import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Абсолютный путь к файлу базы данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "links.db")

def get_db_connection():
    return sqlite3.connect(DB_PATH)

async def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            short_url TEXT,
            long_url TEXT,
            title TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"База данных {DB_PATH} инициализирована или проверена. Файл существует: {os.path.exists(DB_PATH)}")

def save_link(user_id: int, short_url: str, long_url: str, title: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO links (user_id, short_url, long_url, title)
        VALUES (?, ?, ?, ?)
    """, (user_id, short_url, long_url, title))
    conn.commit()
    conn.close()
    logger.info(f"Ссылка {short_url} сохранена для user_id {user_id}")

def get_links_by_user(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, title, short_url, created_at
        FROM links
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (user_id,))
    result = cursor.fetchall()
    conn.close()
    logger.info(f"Найдено {len(result)} ссылок для user_id {user_id}")
    return result

def get_link_by_id(link_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, user_id, short_url, long_url, title, created_at
        FROM links
        WHERE id = ?
    """, (link_id,))
    result = cursor.fetchone()
    conn.close()
    return result

def delete_link(link_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM links WHERE id = ?", (link_id,))
    conn.commit()
    conn.close()
    logger.info(f"Ссылка с id={link_id} удалена")

def rename_link(link_id: int, new_title: str):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE links SET title = ? WHERE id = ?", (new_title, link_id))
    conn.commit()
    conn.close()
    logger.info(f"Ссылка с id={link_id} переименована в {new_title}")
