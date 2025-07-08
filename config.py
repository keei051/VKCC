from os import environ
from dotenv import load_dotenv  # Добавляем для локального использования

# Загружаем .env для локального запуска (опционально)
load_dotenv()  # Убери эту строку, если не хочешь локально

# Получаем токены из переменных окружения
BOT_TOKEN = environ.get("BOT_TOKEN")
VK_TOKEN = environ.get("VK_TOKEN")

# Проверяем, есть ли токены
if not BOT_TOKEN or not VK_TOKEN:
    raise ValueError("Необходимо указать BOT_TOKEN и VK_TOKEN в переменных окружения (или .env для локального запуска).")
