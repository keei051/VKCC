import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_TOKEN = os.getenv("VK_TOKEN")
MAX_LINKS_PER_BATCH = 50
DATABASE_URL = os.getenv("DATABASE_URL")  # postgresql://user:pass@host/db

if not BOT_TOKEN or not VK_TOKEN or not DATABASE_URL:
    raise EnvironmentError("Необходимо указать BOT_TOKEN, VK_TOKEN и DATABASE_URL в переменных окружения.")
