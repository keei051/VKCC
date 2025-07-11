import aiohttp
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def shorten_link(long_url: str, vk_token: str) -> str:
    params = {"url": long_url, "access_token": vk_token, "v": "5.199"}
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://api.vk.com/method/utils.getShortLink", params=params) as resp:
                if resp.status != 200:
                    raise ValueError(f"VK API вернул статус {resp.status}")
                data = await resp.json()
                short_url = data.get("response", {}).get("short_url")
                if short_url:
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
    params = {
        "key": vk_key,
        "access_token": vk_token,
        "v": "5.199",
        "extended": 1,
        "interval": "forever"
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://api.vk.com/method/utils.getLinkStats", params=params) as resp:
                if resp.status != 200:
                    raise ValueError(f"VK API вернул статус {resp.status}")
                data = await resp.json()
                logger.info(f"Ответ VK API для ключа {vk_key}: {data}")
                response_data = data.get("response", {})
                if not response_data.get("views"):
                    return {"views": 0, "message": "Нет данных по этой ссылке"}
                return response_data
        except Exception as e:
            logger.error(f"Сетевая ошибка при получении статистики: {str(e)}")
            raise ValueError(f"Сетевая ошибка: {str(e)}")

