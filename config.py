import os
from dotenv import load_dotenv

# Загружаем .env для локального запуска (опционально)
load_dotenv()

# Получаем токены из переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_TOKEN = os.getenv("VK_TOKEN")

# Проверяем наличие токенов
if not BOT_TOKEN or not VK_TOKEN:
    raise ValueError("Необходимо указать BOT_TOKEN и VK_TOKEN в переменных окружения (или .env для локального запуска).")

# Максимальное количество ссылок за один массовый запрос
MAX_LINKS_PER_BATCH = 50
