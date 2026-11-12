import time
from collections import defaultdict, deque
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from app.config import settings

class AbuseGuardMiddleware(BaseMiddleware):
    """Мягкая защита: не даёт одному пользователю спамить обновлениями."""
    def __init__(self, repo):
        self.repo=repo
        self.events=defaultdict(deque)
        self.warned={}
    async def __call__(self, handler, event: TelegramObject, data: dict):
        uid=getattr(getattr(event, 'from_user', None), 'id', None)
        if not uid:
            return await handler(event,data)
        u=await self.repo.get_user(uid)
        if u and u.blocked and uid not in settings.admin_id_set:
            if hasattr(event,'answer'):
                try: await event.answer('⛔ Ваш доступ к боту временно ограничен администрацией.', show_alert=True)
                except Exception: pass
            return
        now=time.monotonic(); q=self.events[uid]
        while q and now-q[0]>5: q.popleft()
        if len(q)>=8:
            last=self.warned.get(uid,0)
            if now-last>10:
                self.warned[uid]=now
                if hasattr(event,'answer'):
                    try: await event.answer('⏳ Слишком много действий. Подождите несколько секунд.', show_alert=True)
                    except Exception: pass
            return
        q.append(now)
        return await handler(event,data)
