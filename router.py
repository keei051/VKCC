from aiogram import Dispatcher
from handlers import handlers, callback_handlers

def setup_routers(dp: Dispatcher):
    dp.include_router(handlers.router)
    dp.include_router(callback_handlers.router)
