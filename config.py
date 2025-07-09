import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
VK_TOKEN = os.getenv("VK_TOKEN")

if not BOT_TOKEN or not VK_TOKEN:
    raise ValueError("Необходимо указать BOT_TOKEN и VK_TOKEN в переменных окружения.")

MAX_LINKS_PER_BATCH = 50
