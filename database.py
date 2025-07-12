import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


DB_PATH = "links.db"


async def init_db():
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("""
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
            await db.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON links (user_id)")
            await db.commit()
            logger.info("База данных links.db инициализирована или проверена.")
    except Exception as e:
        logger.error(f"Ошибка инициализации базы данных: {e}")


async def is_duplicate_link(user_id: int, original_url: str) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT 1 FROM links WHERE user_id = ? AND original_url = ?",
                (user_id, original_url)
            ) as cursor:
                return await cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Ошибка при проверке дубликата: {e}")
        return False


check_duplicate_link = is_duplicate_link


async def get_link_by_original_url(user_id: int, original_url: str) -> Optional[Tuple]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, user_id, original_url, short_url, title, vk_key, created_at "
                "FROM links WHERE user_id = ? AND original_url = ?",
                (user_id, original_url)
            ) as cursor:
                return await cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка при получении ссылки по исходному URL: {e}")
        return None


async def save_link(user_id: int, original_url: str, short_url: str, title: str, vk_key: str) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute(
                """
                INSERT INTO links (user_id, original_url, short_url, title, vk_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, original_url, short_url, title, vk_key, datetime.now().isoformat())
            )
            await db.commit()
            return True
    except aiosqlite.IntegrityError:
        logger.warning(f"Попытка добавить дубликат short_url: {short_url}")
        return False
    except Exception as e:
        logger.error(f"Ошибка при сохранении ссылки: {e}")
        return False


async def get_links_by_user(user_id: int) -> List[Tuple]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, title, short_url, created_at FROM links WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                return await cursor.fetchall()
    except Exception as e:
        logger.error(f"Ошибка при получении ссылок пользователя: {e}")
        return []


async def get_link_by_id(link_id: int, user_id: int) -> Optional[Tuple]:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            async with db.execute(
                "SELECT id, user_id, original_url, short_url, title, vk_key, created_at "
                "FROM links WHERE id = ? AND user_id = ?",
                (link_id, user_id)
            ) as cursor:
                return await cursor.fetchone()
    except Exception as e:
        logger.error(f"Ошибка при получении ссылки по ID: {e}")
        return None


async def delete_link(link_id: int, user_id: int) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "DELETE FROM links WHERE id = ? AND user_id = ?",
                (link_id, user_id)
            )
            await db.commit()
            if cursor.rowcount == 0:
                logger.warning(f"Попытка удалить несуществующую ссылку: id={link_id}, user_id={user_id}")
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при удалении ссылки: {e}")
        return False


async def rename_link(link_id: int, user_id: int, new_title: str) -> bool:
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cursor = await db.execute(
                "UPDATE links SET title = ? WHERE id = ? AND user_id = ?",
                (new_title, link_id, user_id)
            )
            await db.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Ошибка при переименовании ссылки: {e}")
        return False
