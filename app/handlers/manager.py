from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram import html
quote = html.quote
from app.db.models import Role, STATUS_LABELS
from app.db.repository import Repository
from app.keyboards.common import manager_menu,manager_orders_kb,order_actions
from app.services.notifications import notify_status,notify_price,notify_manager_message
from app.states.forms import PriceForm,MessageForm,ManagerChatForm
router=Router()
async def is_manager(obj,repo):
    from app.services.access import effective_role
    return (await effective_role(obj,repo)) == Role.MANAGER.value
def order_text(o):
    manager_line = f"\n🧑‍🔧 <b>Ответственный:</b> {quote(o.manager.full_name)}" + (f" · @{quote(o.manager.username)}" if o.manager.username else "") if o.manager else "\n🧑‍🔧 <b>Ответственный:</b> не назначен"
    return f"<b>Заявка #{o.id}</b>\n\n👤 {quote(o.user.full_name)} · @{quote(o.user.username) if o.user.username else 'без username'} · ID {o.user.telegram_id}\n📱 {quote(o.category)} / {quote(o.brand_model)}\n🛠 <b>Проблема:</b> {quote(o.problem)}\n🔎 <b>Причина:</b> {quote(o.cause or 'Не указана')}\n📦 <b>Состояние:</b> {quote(o.condition)}\n☎️ {quote(o.phone)}\n\n📌 <b>Статус:</b> {STATUS_LABELS.get(o.status,o.status)}\n💰 <b>Цена:</b> {o.price if o.price is not None else 'не указана'} ₽\n💬 <b>Комментарий:</b> {quote(o.manager_comment) if o.manager_comment else '—'}"
@router.message(F.text=="📥 Новые заявки")
async def new_list(message,repo): await show_list(message,repo,"new",0)
@router.message(F.text=="🔧 В работе")
async def active_list(message,repo): await show_list(message,repo,"in_progress",0)
@router.message(F.text=="📋 Все заявки")
async def all_list(message,repo): await show_list(message,repo,None,0)
@router.message(F.text=="🏁 Завершённые")
async def done_list(message,repo): await show_list(message,repo,"completed",0)
@router.message(F.text=="🔄 Обновить")
async def refresh(message,repo): await message.answer("🔄 Список обновлён.",reply_markup=manager_menu()); await show_list(message,repo,"new",0)
@router.callback_query(F.data.startswith("mgr:list:"))
async def list_cb(call,repo):
    if not await is_manager(call,repo): return await call.answer("Нет доступа",show_alert=True)
    parts=call.data.split(":")
    page=int(parts[2]); status=None if len(parts)<4 or parts[3] in {"all","None"} else parts[3]
    await call.answer(); await show_list(call.message,repo,status,page,edit=True)
async def show_list(message,repo,status,page,edit=False):
    rows,total=await repo.manager_orders(status,page,3)
    title="📥 <b>Новые заявки</b>" if status=="new" else "🔧 <b>В работе</b>" if status=="in_progress" else "🏁 <b>Завершённые</b>" if status=="completed" else "📋 <b>Все заявки</b>"
    text=title+f"\nСтраница {page+1}\n\n"+"\n".join(f"#{o.id} · {quote(o.brand_model)} · {STATUS_LABELS.get(o.status,o.status)}" for o in rows) if rows else title+"\n\nНет заявок."
    markup=manager_orders_kb(rows,page,total,status) if rows else None
    if edit: await message.edit_text(text,reply_markup=markup)
    else: await message.answer(text,reply_markup=markup)
@router.callback_query(F.data.startswith("mgr:order:"))
async def order_detail(call,repo):
    if not await is_manager(call,repo): return await call.answer("Нет доступа",show_alert=True)
    oid=int(call.data.split(":")[-1]); o=await repo.get_order(oid)
    if not o:return await call.answer("Заявка не найдена",show_alert=True)
    await call.answer(); await call.message.edit_text(order_text(o),reply_markup=order_actions(o.id,o.status))
    if o.photo_file_id: await call.message.answer_photo(o.photo_file_id,caption=f"📷 Фото заявки #{o.id}")
@router.callback_query(F.data.startswith("mgr:status:"))
async def status(call,repo):
    if not await is_manager(call,repo): return await call.answer("Нет доступа",show_alert=True)
    _,_,oid,status=call.data.split(":"); manager=await repo.get_user(call.from_user.id)
    if not manager:
        return await call.answer("Не удалось определить менеджера", show_alert=True)
    changed,o,old_status=await repo.update_status(int(oid),status,manager.id)
    if not o:return await call.answer("Заявка не найдена",show_alert=True)
    if not changed:
        if old_status == status:
            return await call.answer("Этот статус уже установлен", show_alert=True)
        return await call.answer("⛔ Такой переход недоступен. Статус заявки можно менять только по логике ремонта.", show_alert=True)
    await notify_status(call.bot,o); await call.answer("Статус обновлён")
    await call.message.edit_text(order_text(o),reply_markup=order_actions(o.id,o.status))
@router.callback_query(F.data.startswith("mgr:price:"))
async def price_start(call,state,repo):
    if not await is_manager(call,repo):
        return await call.answer("Нет доступа", show_alert=True)
    raw_id = call.data.rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        return await call.answer("Заявка не найдена", show_alert=True)
    await state.clear()
    await state.update_data(order_id=int(raw_id))
    await state.set_state(PriceForm.price)
    await call.answer()
    await call.message.answer("💰 Введите цену целым числом в рублях.\n\n/cancel — отмена")
@router.message(PriceForm.price)
async def price(message,state,repo):
    if not await is_manager(message,repo):
        await state.clear()
        return await message.answer("⛔ Режим менеджера завершён.")
    raw=(message.text or "").replace(" ","").replace("₽","")
    if not raw.isdigit() or int(raw)<0 or int(raw)>100000000:return await message.answer("⚠️ Введите сумму от 0 до 100 000 000 ₽.")
    await state.update_data(price=int(raw)); await state.set_state(PriceForm.comment); await message.answer("💬 Добавьте комментарий к цене или напишите «-».")
@router.message(PriceForm.comment)
async def price_comment(message,state,repo):
    if not await is_manager(message,repo):
        await state.clear()
        return await message.answer("⛔ Режим менеджера завершён.")
    d=await state.get_data(); comment=(message.text or "").strip(); comment=None if comment=="-" else comment[:2000]
    manager=await repo.get_user(message.from_user.id)
    changed,o,_=await repo.set_price(d["order_id"],d["price"],comment,manager.id if manager else None); await state.clear()
    if not o:return await message.answer("Заявка не найдена.")
    if changed: await notify_price(message.bot,o)
    await message.answer("✅ Цена сохранена и отправлена клиенту." if changed else "ℹ️ Цена не изменилась; повторное уведомление не отправлялось.",reply_markup=manager_menu())
@router.callback_query(F.data.startswith("mgr:message:"))
async def message_start(call,state,repo):
    if not await is_manager(call,repo):
        return await call.answer("Нет доступа", show_alert=True)
    raw_id = call.data.rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        return await call.answer("Заявка не найдена", show_alert=True)
    await state.clear()
    await state.update_data(order_id=int(raw_id))
    await state.set_state(MessageForm.text)
    await call.answer()
    await call.message.answer("💬 Напишите сообщение клиенту. Оно будет отправлено сразу.\n\n/cancel — отмена")
@router.message(MessageForm.text)
async def message_send(message,state,repo):
    if not await is_manager(message,repo):
        await state.clear()
        return await message.answer("⛔ Режим менеджера завершён.")
    d=await state.get_data(); text=(message.text or "").strip()
    if len(text)<1 or len(text)>2000:return await message.answer("⚠️ Сообщение от 1 до 2000 символов.")
    o=await repo.get_order(d["order_id"]); await state.clear()
    if not o:return await message.answer("Заявка не найдена.")
    await notify_manager_message(message.bot,o,text); await message.answer("✅ Сообщение отправлено клиенту.",reply_markup=manager_menu())

@router.message(F.text=="💬 Чаты")
async def manager_chats(message,repo):
    if not await is_manager(message,repo): return
    rows,total=await repo.manager_orders(None,0,50)
    rows=[o for o in rows if o.status not in {"cancelled","completed"}]
    if not rows:return await message.answer("💬 <b>Чаты</b>\n\nАктивных клиентских чатов пока нет.",reply_markup=manager_menu())
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b=InlineKeyboardBuilder()
    for o in rows:b.button(text=f"💬 #{o.id} · {o.brand_model[:22]}",callback_data=f"chat:mgr:{o.id}")
    b.adjust(1); await message.answer("💬 <b>Клиентские чаты</b>\n\nВыберите заявку:",reply_markup=b.as_markup())

@router.callback_query(F.data.startswith("chat:mgr:"))
async def manager_chat_open(call,state,repo):
    if not await is_manager(call,repo):
        return await call.answer("Нет доступа", show_alert=True)
    raw_id = call.data.rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        return await call.answer("Чат не найден", show_alert=True)
    oid = int(raw_id)
    o = await repo.get_order(oid)
    if not o or not o.user:
        return await call.answer("Заявка или клиент не найдены", show_alert=True)
    await state.clear()
    await state.update_data(chat_order_id=oid, chat_role=Role.MANAGER.value)
    await state.set_state(ManagerChatForm.text)
    await call.answer()
    await show_manager_chat(call.message, repo, o, edit=True)
    await call.message.answer("✍️ Напишите сообщение клиенту.\n\n/cancel — закрыть чат")

@router.message(ManagerChatForm.text)
async def manager_chat_send(message,state,repo):
    if not await is_manager(message,repo): return
    d=await state.get_data()
    if d.get("chat_role")!=Role.MANAGER.value:return
    oid=d.get("chat_order_id"); text=(message.text or "").strip()
    if not oid:return await state.clear()
    if not 1<=len(text)<=2000:return await message.answer("⚠️ Сообщение от 1 до 2000 символов.")
    o=await repo.get_order(oid)
    if not o or not o.user:
        await state.clear()
        return await message.answer("Заявка или клиент не найдены.", reply_markup=manager_menu())
    u=await repo.get_user(message.from_user.id)
    if not u:
        await state.clear()
        return await message.answer("Не удалось определить менеджера.", reply_markup=manager_menu())
    await repo.assign_manager(oid,u.id)
    await repo.add_chat_message(oid,u.id,Role.MANAGER.value,text)
    try: await message.bot.send_message(o.user.telegram_id,f"💬 <b>Менеджер по заявке #{oid}</b>\n\n{html.quote(text)}")
    except Exception: pass
    await message.answer("✅ Сообщение отправлено клиенту.")
    await show_manager_chat(message,repo,o)

async def show_manager_chat(message,repo,o,edit=False):
    msgs=await repo.chat_messages(o.id,30)
    lines=[f"💬 <b>Чат с клиентом · заявка #{o.id}</b>",f"👤 {html.quote(o.user.full_name)} · {STATUS_LABELS.get(o.status,o.status)}"," "]
    if not msgs: lines.append("Сообщений пока нет.")
    for m in msgs:
        who="👤 Клиент" if m.sender_role==Role.USER.value else "🧑‍🔧 Вы"
        lines.append(f"<b>{who}</b> · {m.created_at:%d.%m %H:%M}\n{html.quote(m.text)}")
    markup=__import__('app.keyboards.common',fromlist=['chat_kb']).chat_kb(o.id,"mgr:list:0")
    if edit: await message.edit_text("\n\n".join(lines),reply_markup=markup)
    else: await message.answer("\n\n".join(lines),reply_markup=markup)

@router.message(F.text=="📈 Сводка дня")
async def daily_summary(message,repo):
    if not await is_manager(message,repo): return
    from datetime import datetime, timedelta
    now=datetime.now(); start=now.replace(hour=0,minute=0,second=0,microsecond=0)
    rows=await repo.all_orders(start,now+timedelta(seconds=1))
    new=sum(o.status=="new" for o in rows); active=sum(o.status in {"accepted","in_progress","waiting_parts","ready"} for o in rows); done=sum(o.status=="completed" for o in rows)
    await message.answer(f"📈 <b>Сводка дня</b>\n\n🧾 Заявок сегодня: <b>{len(rows)}</b>\n🆕 Новых: <b>{new}</b>\n🔧 В работе: <b>{active}</b>\n🏁 Завершено: <b>{done}</b>",reply_markup=manager_menu())
