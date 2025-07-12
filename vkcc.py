import logging
from typing import TypedDict

from session import session
from config import VK_TOKEN

VK_API_BASE = "https://api.vk.com/method/"
VK_API_VERSION = "5.199"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FullLinkStats(TypedDict, total=False):
    views: int
    stats: list
    sex_age: list
    countries: list
    cities: list
    message: str

async def shorten_link(long_url: str, vk_token: str) -> str:
    params = {
        "url": long_url,
        "access_token": vk_token,
        "v": VK_API_VERSION
    }
    try:
        async with session.get(f"{VK_API_BASE}utils.getShortLink", params=params) as resp:
            if resp.status != 200:
                raise ValueError(f"VK API вернул статус {resp.status}")
            data = await resp.json()
            if "error" in data:
                error_msg = data["error"].get("error_msg", "Неизвестная ошибка")
                raise ValueError(f"VK API ошибка: {error_msg}")
            short_url = data.get("response", {}).get("short_url")
            if short_url:
                logger.info(f"Сократил ссылку: {long_url} -> {short_url}")
                return short_url
            raise ValueError("VK API не вернул short_url")
    except Exception as e:
        logger.error(f"Ошибка при сокращении ссылки: {e}")
        raise ValueError(f"Сетевая ошибка: {e}")

async def get_link_stats(vk_key: str, vk_token: str) -> FullLinkStats:
    params = {
        "key": vk_key,
        "access_token": vk_token,
        "v": VK_API_VERSION,
        "extended": 1,
        "interval": "forever"
    }
    try:
        async with session.get(f"{VK_API_BASE}utils.getLinkStats", params=params) as resp:
            if resp.status != 200:
                raise ValueError(f"VK API вернул статус {resp.status}")
            data = await resp.json()
            if "error" in data:
                error_msg = data["error"].get("error_msg", "Неизвестная ошибка")
                raise ValueError(f"VK API ошибка: {error_msg}")

            response_data = data.get("response", {})
            if "views" not in response_data:
                return {"views": 0, "message": "Нет данных по этой ссылке"}

            return {
                "views": response_data.get("views", 0),
                "stats": response_data.get("stats", []),
                "sex_age": response_data.get("sex_age", []),
                "countries": response_data.get("countries", []),
                "cities": response_data.get("cities", [])
            }

    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {e}")
        raise ValueError(f"Сетевая ошибка: {e}")
