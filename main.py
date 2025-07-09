import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, VK_TOKEN
from handlers import setup_handlers
from database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    bot = Bot(token=BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher()
    await init_db()
    setup_handlers(dp)
    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")

if __name__ == "__main__":
    asyncio.run(main())
