import asyncio
import logging
import gettext
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.strategy import FSMStrategy

from config import BOT_TOKEN
from routers.handlers import router as handlers_router
from database import init_db
from session import create_session, close_session
from middleware.throttle import ThrottlingMiddleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# i18n setup
gettext.install('bot', localedir='locale')

async def main():
    await create_session()
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher(fsm_strategy=FSMStrategy.USER_IN_CHAT)
    await init_db()
    dp.include_router(handlers_router)
    dp.message.middleware(ThrottlingMiddleware())
    logger.info("Бот запущен!")
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Ошибка при запуске: {e}")
    finally:
        await close_session()
        logger.info("HTTP-сессия закрыта. Бот завершил работу.")

if __name__ == "__main__":
    asyncio.run(main())
