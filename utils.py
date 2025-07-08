import re
import logging
from aiogram.types import Message
from geopy.geocoders import Nominatim  # Для примерного местоположения (заглушка)

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

async def get_user_location(user_id: int) -> str:
    # Заглушка: реальное местоположение требует API (например, Telegram Passport или IP API)
    # Здесь примерное значение, можно улучшить с использованием geopy или другого сервиса
    geolocator = Nominatim(user_agent="vkcc_bot")
    try:
        location = geolocator.geocode("Unknown")  # Замени на реальный IP или данные
        return location.address if location else "Неизвестное местоположение"
    except Exception:
        return "Неизвестное местоположение"

def format_link_stats(stats: dict, short_url: str) -> str:
    if not stats or "views" not in stats:
        return f"📉 Пока нет статистики по {short_url}.\nПопробуйте позже."
    
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
        response += "\n🌍 География (страны):\n"
        for country in stats["countries"]:
            country_name = "Неизвестно"  # Требуется парсер для country_id
            views = country["views"]
            response += f"— {country_name}: {views} ({views/stats['views']*100:.1f}%)\n"
        if "cities" in stats:
            response += "Города:\n"
            for city in stats["cities"]:
                city_name = "Неизвестно"  # Требуется парсер для city_id
                views = city["views"]
                response += f"  — {city_name}: {views} ({views/stats['views']*100:.1f}%)\n"

    return response
