import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from config import BOT_TOKEN, VK_TOKEN
from handlers import setup_handlers
from database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher()

    # Подключение базы данных
    await init_db()

    # Регистрация хендлеров
    setup_handlers(dp)

    logger.info("Бот запущен!")

    # Запуск бота
    try:
        await dp.start_polling(bot)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен вручную.")
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")

if __name__ == "__main__":
    asyncio.run(main())
