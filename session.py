import aiohttp
import logging

logger = logging.getLogger(__name__)
session: aiohttp.ClientSession = None

async def create_session():
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
        logger.info("HTTP-сессия создана.")

async def close_session():
    global session
    if session and not session.closed:
        await session.close()
        logger.info("HTTP-сессия закрыта.")
        session = None
