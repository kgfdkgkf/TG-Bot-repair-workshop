import asyncio,logging
from aiogram import Bot,Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from app.config import settings
from app.database import create_database
from app.db.repository import Repository
from app.handlers import start,auth,user,manager,admin,fallback
from app.middlewares.errors import ErrorMiddleware
from app.middlewares.guard import AbuseGuardMiddleware
async def main():
    logging.basicConfig(level=logging.INFO)
    engine,sf=await create_database(settings.database_url); repo=Repository(sf)
    bot=Bot(settings.bot_token,default=DefaultBotProperties(parse_mode=ParseMode.HTML)); dp=Dispatcher(storage=MemoryStorage()); dp["repo"]=repo
    dp.message.middleware(ErrorMiddleware()); dp.callback_query.middleware(ErrorMiddleware())
    dp.message.middleware(AbuseGuardMiddleware(repo)); dp.callback_query.middleware(AbuseGuardMiddleware(repo))
    dp.include_router(start.router); dp.include_router(auth.router); dp.include_router(user.router); dp.include_router(manager.router); dp.include_router(admin.router); dp.include_router(fallback.router)
    await bot.delete_webhook(drop_pending_updates=True)
    try: await dp.start_polling(bot,repo=repo)
    finally: await bot.session.close(); await engine.dispose()
if __name__=="__main__": asyncio.run(main())
