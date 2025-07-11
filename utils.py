import re
import logging
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def safe_delete(message: Message):
    try:
        await message.delete()
    except Exception as e:
        logger.debug(f"Не удалось удалить сообщение: {e}")

def is_valid_url(url: str) -> bool:
    url = url.strip()
    if not url:
        return False
    pattern = re.compile(
        r'^https?://'
        r'(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}|'  # домен
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IPv4
        r'(?::\d+)?(?:/[-a-zA-Z0-9@:%_\+.~#?&//=]*)?$'
    )
    return bool(pattern.match(url))

def format_link_stats(stats: dict, short_url: str) -> str:
    if not stats or stats.get("views", 0) == 0:
        return f"📉 Статистика по <b>{short_url}</b> отсутствует. Ожидайте переходы."

    total_views = stats.get("views", 1)
    response = [f"<b>📊 Статистика по {short_url}</b>",
                f"<b>Всего переходов:</b> {total_views}\n"]

    # Пол и возраст
    if "sex_age" in stats:
        response.append("<b>👥 Топ-3 возрастные группы:</b>")
        sex_map = {1: "мужчины", 2: "женщины"}
        top_groups = sorted(stats["sex_age"], key=lambda x: x.get("views", 0), reverse=True)[:3]
        for group in top_groups:
            age = group.get("age_range", "?")
            sex = sex_map.get(group.get("sex"), "неизвестно")
            views = group.get("views", 0)
            percent = views / total_views * 100 if total_views else 0
            response.append(f"– {sex}, {age}: {views} ({percent:.1f}%)")

    # Страны
    if "countries" in stats:
        country_map = {
            1: "Россия", 2: "Украина", 3: "Беларусь", 4: "Казахстан", 5: "Германия",
            7: "Финляндия", 10: "США", 13: "Франция", 14: "Италия", 17: "Испания"
        }
        top_countries = sorted(stats["countries"], key=lambda x: x["views"], reverse=True)[:3]
        response.append("\n<b>🌍 Страны:</b>")
        for c in top_countries:
            cid = c.get("country_id")
            views = c.get("views", 0)
            name = country_map.get(cid, f"ID {cid}")
            percent = views / total_views * 100 if total_views else 0
            response.append(f"– {name}: {views} ({percent:.1f}%)")

    # Города
    if "cities" in stats:
        city_map = {
            1: "Москва", 2: "Санкт-Петербург", 99: "Уфа", 56: "Казань",
            3: "Новосибирск", 4: "Екатеринбург", 66: "Нижний Новгород"
        }
        top_cities = sorted(stats["cities"], key=lambda x: x["views"], reverse=True)[:3]
        response.append("\n<b>🏙️ Города:</b>")
        for c in top_cities:
            cid = c.get("city_id")
            views = c.get("views", 0)
            name = city_map.get(cid, f"ID {cid}")
            percent = views / total_views * 100 if total_views else 0
            response.append(f"– {name}: {views} ({percent:.1f}%)")

    return "\n".join(response)
