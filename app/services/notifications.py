import logging
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramForbiddenError
from aiogram import html
quote = html.quote
from app.db.models import Order, STATUS_LABELS
log=logging.getLogger(__name__)
async def safe_notify(bot: Bot, telegram_id: int, text: str):
    try: await bot.send_message(telegram_id,text); return True
    except TelegramForbiddenError: log.info("User %s blocked bot",telegram_id); return False
    except TelegramAPIError as e: log.warning("Notification failed for %s: %s",telegram_id,e); return False
    except Exception as e: log.exception("Unexpected notification error: %s",e); return False
async def notify_status(bot, order):
    return await safe_notify(bot, order.user.telegram_id, f"🔔 <b>Заявка #{order.id}</b>\nНовый статус: <b>{STATUS_LABELS.get(order.status,order.status)}</b>")
async def notify_price(bot, order):
    text=f"💰 <b>Заявка #{order.id}</b>\nМенеджер указал стоимость: <b>{order.price:,} ₽</b>".replace(","," ")
    if order.manager_comment: text += f"\nКомментарий: {quote(order.manager_comment)}"
    return await safe_notify(bot, order.user.telegram_id,text)
async def notify_manager_message(bot, order, text):
    return await safe_notify(bot, order.user.telegram_id, f"💬 <b>Сообщение по заявке #{order.id}</b>\n\n{text}")
