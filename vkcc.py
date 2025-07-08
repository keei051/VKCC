import aiohttp
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def shorten_link(long_url: str, vk_token: str) -> str:
    """
    Сокращает длинную ссылку через VK.cc API.
    """
    params = {
        "url": long_url,
        "access_token": vk_token,
        "v": "5.199"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://api.vk.com/method/utils.getShortLink", params=params) as resp:
                data = await resp.json()
                if "response" in data and "short_url" in data["response"]:
                    short_url = data["response"]["short_url"]
                    logger.info(f"Успешно сократил ссылку: {long_url} -> {short_url}")
                    return short_url
                else:
                    error_msg = data.get("error", {}).get("error_msg", "Неизвестная ошибка")
                    logger.error(f"Ошибка сокращения ссылки: {error_msg}")
                    raise ValueError(f"Не удалось сократить ссылку: {error_msg}")
        except Exception as e:
            logger.error(f"Сетевая ошибка при сокращении: {str(e)}")
            raise ValueError(f"Сетевая ошибка: {str(e)}")

async def get_link_stats(vk_key: str, vk_token: str) -> dict:
    """
    Получает статистику по сокращённой ссылке через VK.cc API.
    Возвращает данные о переходах, гео, пол/возраст.
    """
    params = {
        "key": vk_key,
        "access_token": vk_token,
        "v": "5.199",
        "extended": 1,  # Полная статистика (гео, пол/возраст)
        "interval": "forever"  # Статистика за всё время
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://api.vk.com/method/utils.getLinkStats", params=params) as resp:
                data = await resp.json()
                logger.info(f"Ответ VK API для ключа {vk_key}: {data}")  # Отладка
                if "response" in data:
                    response_data = data["response"]
                    if not response_data.get("views", 0) and not response_data.get("stats") and not response_data.get("sex_age"):
                        return {"views": 0, "message": "Нет данных по этой ссылке"}
                    return response_data
                else:
                    error_msg = data.get("error", {}).get("error_msg", "Неизвестная ошибка")
                    logger.error(f"Ошибка получения статистики: {error_msg}")
                    raise ValueError(f"Не удалось получить статистику: {error_msg}")
        except Exception as e:
            logger.error(f"Сетевая ошибка при получении статистики: {str(e)}")
            raise ValueError(f"Сетевая ошибка: {str(e)}")
