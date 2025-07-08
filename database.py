import aiosqlite
from datetime import datetime

async def init_db():
    async with aiosqlite.connect("links.db") as db:
        # Создаём таблицу без индекса
        await db.execute("""
            CREATE TABLE IF NOT EXISTS links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                long_url TEXT NOT NULL,
                short_url TEXT NOT NULL,
                title TEXT,
                vk_key TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        # Создаём индекс отдельно
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_id ON links (user_id)
        """)
        await db.commit()

async def save_link(user_id: int, long_url: str, short_url: str, title: str, vk_key: str):
    try:
        async with aiosqlite.connect("links.db") as db:
            cursor = await db.execute(
                "SELECT id FROM links WHERE user_id = ? AND short_url = ?",
                (user_id, short_url)
            )
            if await cursor.fetchone():
                return False
            await db.execute(
                "INSERT INTO links (user_id, long_url, short_url, title, vk_key, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, long_url, short_url, title or "Без подписи", vk_key, datetime.now().isoformat())
            )
            await db.commit()
            return True
    except Exception as e:
        print(f"DB Error: {e}")
        return False

async def get_links_by_user(user_id: int):
    try:
        async with aiosqlite.connect("links.db") as db:
            cursor = await db.execute(
                "SELECT id, title, short_url, created_at FROM links WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,)
            )
            return await cursor.fetchall()
    except Exception as e:
        print(f"DB Error: {e}")
        return []

async def get_link_by_id(link_id: int, user_id: int):
    try:
        async with aiosqlite.connect("links.db") as db:
            cursor = await db.execute(
                "SELECT id, user_id, long_url, short_url, title, vk_key, created_at FROM links WHERE id = ? AND user_id = ?",
                (link_id, user_id)
            )
            return await cursor.fetchone()
    except Exception as e:
        print(f"DB Error: {e}")
        return None

async def delete_link(link_id: int, user_id: int):
    try:
        async with aiosqlite.connect("links.db") as db:
            cursor = await db.execute(
                "DELETE FROM links WHERE id = ? AND user_id = ?",
                (link_id, user_id)
            )
            await db.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"DB Error: {e}")
        return False

async def rename_link(link_id: int, user_id: int, new_title: str):
    try:
        async with aiosqlite.connect("links.db") as db:
            await db.execute(
                "UPDATE links SET title = ? WHERE id = ? AND user_id = ?",
                (new_title, link_id, user_id)
            )
            await db.commit()
            return True
    except Exception as e:
        print(f"DB Error: {e}")
        return False
