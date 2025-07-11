import aiohttp

session: aiohttp.ClientSession = None

async def create_session():
    global session
    session = aiohttp.ClientSession()

async def close_session():
    global session
    if session:
        await session.close()
        session = None
