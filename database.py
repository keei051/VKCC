import sqlite3
import logging
from datetime import datetime
from contextlib import contextmanager
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


@contextmanager
def get_connection():
    conn = sqlite3.connect("links.db")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    original_url TEXT,
                    short_url TEXT UNIQUE,
                    title TEXT,
                    vk_key TEXT,
                    created_at TEXT
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON links (user_id)")
            conn.commit()
            logger.info("База данных links.db инициализирована или проверена.")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")


def is_duplicate_link(user_id: int, original_url: str) -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM links WHERE user_id = ? AND original_url = ?",
                (user_id, original_url)
            )
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке дубликата: {e}")
        return False

# Alias for handlers
check_duplicate_link = is_duplicate_link


def get_link_by_original_url(user_id: int, original_url: str) -> Optional[Tuple]:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, user_id, original_url, short_url, title, vk_key, created_at"
                " FROM links WHERE user_id = ? AND original_url = ?",
                (user_id, original_url)
            )
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка при получении ссылки по исходному URL: {e}")
        return None


def save_link(user_id: int, original_url: str, short_url: str, title: str, vk_key: str) -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO links (user_id, original_url, short_url, title, vk_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, original_url, short_url, title, vk_key, datetime.now().isoformat())
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        logger.warning(f"Попытка добавить дубликат short_url: {short_url}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при сохранении ссылки: {e}")
        return False


def get_links_by_user(user_id: int) -> List[Tuple]:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, title, short_url, created_at FROM links WHERE user_id = ?",
                (user_id,)
            )
            return cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка при получении ссылок пользователя: {e}")
        return []


def get_link_by_id(link_id: int, user_id: int) -> Optional[Tuple]:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, user_id, original_url, short_url, title, vk_key, created_at"
                " FROM links WHERE id = ? AND user_id = ?",
                (link_id, user_id)
            )
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка при получении ссылки по ID: {e}")
        return None


def delete_link(link_id: int, user_id: int) -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM links WHERE id = ? AND user_id = ?",
                (link_id, user_id)
            )
            conn.commit()
            if cursor.rowcount == 0:
                logger.warning(f"Попытка удалить несуществующую ссылку: id={link_id}, user_id={user_id}")
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении ссылки: {e}")
        return False


def rename_link(link_id: int, user_id: int, new_title: str) -> bool:
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE links SET title = ? WHERE id = ? AND user_id = ?",
                (new_title, link_id, user_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при переименовании ссылки: {e}")
        return False
