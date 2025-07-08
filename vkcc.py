import aiohttp
from config import VK_TOKEN

async def shorten_link(long_url: str) -> str:
    params = {
        "url": long_url,
        "access_token": VK_TOKEN,
        "v": "5.199"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.vk.com/method/utils.getShortLink", params=params) as resp:
            data = await resp.json()
            if "response" in data and "short_url" in data["response"]:
                return data["response"]["short_url"]
            raise ValueError(data.get("error", {}).get("error_msg", "Не удалось сократить ссылку"))

async def get_link_stats(vk_key: str) -> dict:
    params = {
        "key": vk_key,
        "access_token": VK_TOKEN,
        "v": "5.199",
        "extended": 1,
        "interval": "forever"
    }
    async with aiohttp.ClientSession() as session:
        async with session.get("https://api.vk.com/method/utils.getLinkStats", params=params) as resp:
            data = await resp.json()
            if "response" in data:
                return data["response"]
            raise ValueError(data.get("error", {}).get("error_msg", "Не удалось получить статистику"))
