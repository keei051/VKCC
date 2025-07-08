import re
import logging
from aiogram.types import Message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def safe_delete(message: Message):
    try:
        await message.delete()
    except:
        pass  # Если сообщение уже удалено или недоступно

def is_valid_url(url: str) -> bool:
    url = url.strip()
    if not url:
        return False
    pattern = re.compile(
        r'^https?://'  # http:// или https://
        r'(?:(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,}|'  # домен
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?(?:/[-a-zA-Z0-9@:%_\+.~#?&//=]*)?$'
    )
    return bool(pattern.match(url))

def format_link_stats(stats: dict, short_url: str) -> str:
    if not stats or "views" not in stats or stats.get("views", 0) == 0:
        return f"📉 Пока нет статистики по {short_url}.\nПопробуйте позже, когда будут переходы."
    
    response = f"📊 Статистика по {short_url}\n"
    response += f"👁 Переходов: {stats.get('views', 0)}\n\n"

    if "sex_age" in stats:
        sex_age = {}
        for item in stats["sex_age"]:
            age_range = item["age_range"]
            sex = "Мужчины" if item["sex"] == 1 else "Женщины"
            views = item["views"]
            sex_age.setdefault(age_range, {}).setdefault(sex, 0)
            sex_age[age_range][sex] += views
        response += "👤 Пол / возраст:\n"
        for age, sexes in sex_age.items():
            men = sexes.get("Мужчины", 0)
            women = sexes.get("Женщины", 0)
            total = men + women
            if total > 0:
                response += f"— {age}: Мужчины {men/total*100:.0f}%, Женщины {women/total*100:.0f}%\n"

    if "countries" in stats:
        response += "\n🌍 География (переходы):\n"
        total_views = stats.get("views", 1)  # Избегаем деления на ноль
        for country in stats["countries"]:
            country_id = country["country_id"]
            views = country["views"]
            country_name = "Неизвестная страна"  # Требуется парсер для country_id (например, через справочник)
            response += f"— {country_name} (ID {country_id}): {views} ({views/total_views*100:.1f}%)\n"
        if "cities" in stats:
            response += "Города:\n"
            for city in stats["cities"]:
                city_id = city["city_id"]
                views = city["views"]
                city_name = "Неизвестный город"  # Требуется парсер для city_id
                response += f"  — {city_name} (ID {city_id}): {views} ({views/total_views*100:.1f}%)\n"

    return response
