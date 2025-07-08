import asyncio
import logging
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN, VK_TOKEN
from handlers import setup_handlers
from database import init_db

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Инициализация бота и диспетчера
    bot = Bot(token=BOT_TOKEN)
    await bot.delete_webhook(drop_pending_updates=True)  # Удаляем вебхук для избежания конфликтов
    dp = Dispatcher()
    
    # Инициализация базы данных
    await init_db()
    
    # Настройка обработчиков
    setup_handlers(dp)
    
    # Запуск бота
    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")

if __name__ == "__main__":
    asyncio.run(main())
