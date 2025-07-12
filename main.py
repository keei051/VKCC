import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from config import BOT_TOKEN
from handlers import setup_handlers
from database import init_db  # ✅ Синхронная функция — без await
from session import create_session, close_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Инициализация VK-сессии
    await create_session()

    # Создание бота и диспетчера
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    # Удаляем старые вебхуки и дропаем подвисшие апдейты
    await bot.delete_webhook(drop_pending_updates=True)

    # Инициализация базы данных
    init_db()  # 🟢 без await

    # Подключаем все хендлеры
    setup_handlers(dp)

    logger.info("Бот запущен и готов принимать команды.")

    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.exception(f"Ошибка во время работы бота: {e}")
    finally:
        await close_session()
        logger.info("HTTP-сессия закрыта. Бот завершил работу.")

if __name__ == "__main__":
    asyncio.run(main())
