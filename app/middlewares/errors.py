import logging
from aiogram import BaseMiddleware
log=logging.getLogger(__name__)
class ErrorMiddleware(BaseMiddleware):
    async def __call__(self,handler,event,data):
        try:return await handler(event,data)
        except Exception:
            log.exception("Unhandled bot error")
            if hasattr(event,"answer"):
                try: await event.answer("⚠️ Произошла внутренняя ошибка. Попробуйте ещё раз.")
                except Exception: pass
            return None
