import aiosqlite
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

async def init_db():
    async with aiosqlite.connect('links.db') as conn:
        try:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    original_url TEXT,
                    short_url TEXT UNIQUE,
                    title TEXT,
                    vk_key TEXT,
                    created_at DATETIME
                )
            """)
            await conn.commit()
            logger.info("База данных /app/links.db инициализирована или проверена. Файл существует: True")
        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")

async def check_duplicate_link(user_id: int, original_url: str) -> bool:
    async with aiosqlite.connect('links.db') as conn:
        try:
            cursor = await conn.execute(
                "SELECT 1 FROM links WHERE user_id = ? AND original_url = ?",
                (user_id, original_url)
            )
            exists = await cursor.fetchone() is not None
            if exists:
                logger.info(f"Дубликат ссылки найден: user_id={user_id}, url={original_url}")
            return exists
        except Exception as e:
            logger.error(f"Ошибка проверки дубликата ссылки: {e}")
            return False

async def save_link(user_id: int, original_url: str, short_url: str, title: str, vk_key: str) -> bool:
    async with aiosqlite.connect('links.db') as conn:
        try:
            await conn.execute(
                """
                INSERT INTO links (user_id, original_url, short_url, title, vk_key, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, original_url, short_url, title, vk_key, datetime.now())
            )
            await conn.commit()
            logger.info(f"Ссылка сохранена: user_id={user_id}, short_url={short_url}")
            return True
        except aiosqlite.IntegrityError:
            logger.error(f"Ссылка уже существует: {short_url}")
            return False
        except Exception as e:
            logger.error(f"Ошибка сохранения ссылки: {e}")
            return False

async def get_links_by_user(user_id: int) -> list:
    async with aiosqlite.connect('links.db') as conn:
        try:
            cursor = await conn.execute(
                "SELECT id, title, short_url, created_at FROM links WHERE user_id = ?",
                (user_id,)
            )
            links = await cursor.fetchall()
            logger.info(f"Найдено {len(links)} ссылок для user_id {user_id}")
            return links
        except Exception as e:
            logger.error(f"Ошибка получения ссылок: {e}")
            return []

async def get_link_by_id(link_id: int, user_id: int) -> tuple:
    async with aiosqlite.connect('links.db') as conn:
        try:
            cursor = await conn.execute(
                "SELECT id, user_id, original_url, short_url, title, vk_key, created_at FROM links WHERE id = ? AND user_id = ?",
                (link_id, user_id)
            )
            link = await cursor.fetchone()
            return link if link else None
        except Exception as e:
            logger.error(f"Ошибка получения ссылки: {e}")
            return None

async def delete_link(link_id: int, user_id: int) -> bool:
    async with aiosqlite.connect('links.db') as conn:
        try:
            cursor = await conn.execute(
                "DELETE FROM links WHERE id = ? AND user_id = ?",
                (link_id, user_id)
            )
            await conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка удаления ссылки: {e}")
            return False

async def rename_link(link_id: int, user_id: int, new_title: str) -> bool:
    async with aiosqlite.connect('links.db') as conn:
        try:
            cursor = await conn.execute(
                "UPDATE links SET title = ? WHERE id = ? AND user_id = ?",
                (new_title, link_id, user_id)
            )
            await conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Ошибка переименования ссылки: {e}")
            return False
