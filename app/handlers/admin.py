from datetime import datetime,timedelta
from aiogram import F,Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery,Message,BufferedInputFile
from aiogram import html
quote = html.quote
from app.config import settings
from app.db.models import Role,STATUS_LABELS
from app.db.repository import Repository
from app.keyboards.common import admin_menu,admin_status_kb,admin_orders_page_kb
from app.services.export import build_report
from app.states.forms import ManagerForm,ReportForm,AdminForm
router=Router()
async def is_admin(obj,repo):
    # Для админов учитываем выбранный режим интерфейса: в режиме
    # пользователя/менеджера системные кнопки не должны вмешиваться.
    from app.services.access import effective_role
    return (await effective_role(obj, repo)) == Role.ADMIN.value
@router.message(F.text=="📊 Дашборд")
async def dashboard(message,repo):
    if not await is_admin(message,repo): return
    s=await repo.stats(); await message.answer(f"📊 <b>Системный дашборд</b>\n\n👥 Пользователи: <b>{s['users']}</b>\n📋 Заявки: <b>{s['orders']}</b>\n🆕 Новые: <b>{s['new']}</b>\n🔧 Активные: <b>{s['active']}</b>\n🏁 Завершённые: <b>{s['completed']}</b>\n💰 Сумма завершённых: <b>{s['revenue']:,} ₽</b>".replace(","," "),reply_markup=admin_menu())
@router.message(F.text=="🔎 Заявки")
async def orders(message,repo):
    if not await is_admin(message,repo): return
    await message.answer("🔎 <b>Фильтр заявок</b>\nВыберите статус:",reply_markup=admin_status_kb())
@router.callback_query(F.data=="adm:home")
async def home(call,repo):
    if not await is_admin(call,repo):return await call.answer("Нет доступа",show_alert=True)
    await call.answer(); await call.message.answer("⚙️ Системное меню администратора",reply_markup=admin_menu())
@router.callback_query(F.data=="adm:order_filter")
async def filter_menu(call,repo): await call.answer(); await call.message.edit_text("Выберите статус:",reply_markup=admin_status_kb())
@router.callback_query(F.data.startswith("adm:orders:"))
async def order_filter(call,repo):
    if not await is_admin(call,repo):return await call.answer("Нет доступа",show_alert=True)
    _,_,status,page=call.data.split(":"); status=None if status=="all" else status; page=int(page)
    rows,total=await repo.manager_orders(status,page,5); title="Все" if status is None else STATUS_LABELS.get(status,status)
    text=f"🔎 <b>{title}</b> · всего {total}\n\n"+"\n".join(f"#{o.id} · {quote(o.user.full_name)} · {quote(o.brand_model)} · {STATUS_LABELS.get(o.status,o.status)} · {quote(o.manager.full_name) if o.manager else 'менеджер не назначен'} · {o.price or 0} ₽" for o in rows) if rows else f"🔎 <b>{title}</b>\n\nНет заявок."
    await call.answer(); await call.message.edit_text(text,reply_markup=admin_orders_page_kb(status or "all",page,total,rows))
@router.callback_query(F.data.startswith("adm:order:"))
async def admin_order_detail(call,repo):
    if not await is_admin(call,repo): return await call.answer("Нет доступа",show_alert=True)
    oid=int(call.data.split(":")[-1]); o=await repo.get_order(oid)
    if not o: return await call.answer("Заявка не найдена",show_alert=True)
    manager_line=(f"🧑‍🔧 <b>Менеджер:</b> {quote(o.manager.full_name)}" + (f" · @{quote(o.manager.username)}" if o.manager.username else "")) if o.manager else "🧑‍🔧 <b>Менеджер:</b> ещё не назначен"
    text=(f"🔎 <b>Заявка #{o.id}</b>\n\n"
          f"👤 <b>Клиент:</b> {quote(o.user.full_name)}\n"
          f"👤 <b>Username:</b> @{quote(o.user.username) if o.user.username else 'не указан'}\n"
          f"🆔 <b>Telegram ID:</b> <code>{o.user.telegram_id}</code>\n\n"
          f"📱 <b>Устройство:</b> {quote(o.category)}\n"
          f"🏷 <b>Модель / конфигурация:</b> {quote(o.brand_model)}\n"
          f"🛠 <b>Проблема:</b> {quote(o.problem)}\n"
          f"🔎 <b>Причина:</b> {quote(o.cause or 'Не указана')}\n"
          f"📦 <b>Состояние:</b> {quote(o.condition)}\n"
          f"☎️ <b>Телефон:</b> {quote(o.phone)}\n"
          f"{manager_line}\n\n"
          f"📌 <b>Статус:</b> {STATUS_LABELS.get(o.status,o.status)}\n"
          f"💰 <b>Цена:</b> {o.price if o.price is not None else 'не указана'} ₽\n"
          f"💬 <b>Комментарий:</b> {quote(o.manager_comment) if o.manager_comment else '—'}")
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b=InlineKeyboardBuilder(); b.button(text="⬅️ К списку",callback_data="adm:orders:all:0"); b.adjust(1)
    await call.answer(); await call.message.edit_text(text,reply_markup=b.as_markup())
    if o.photo_file_id: await call.message.answer_photo(o.photo_file_id,caption=f"📷 Фото заявки #{o.id}")

@router.message(F.text=="📈 Работа менеджеров")
async def manager_workload(message,repo):
    if not await is_admin(message,repo): return
    rows=await repo.manager_stats()
    if not rows: return await message.answer("📈 <b>Работа менеджеров</b>\n\nМенеджеров пока нет.",reply_markup=admin_menu())
    lines=["📈 <b>Работа менеджеров</b>","","Показатели по всем заявкам:"]
    for u,total,active,done in rows:
        uname=f" · @{quote(u.username)}" if u.username else ""
        lines.append(f"\n🧑‍🔧 <b>{quote(u.full_name)}</b>{uname}\n📋 Всего: <b>{total}</b> · 🔧 Активных: <b>{active}</b> · 🏁 Завершено: <b>{done}</b>")
    await message.answer("\n".join(lines),reply_markup=admin_menu())

@router.message(F.text=="👥 Менеджеры")
async def managers(message,repo):
    if not await is_admin(message,repo):return
    await show_managers(message,repo)

async def show_managers(message,repo):
    ms=await repo.managers()
    if not ms:return await message.answer("👥 Менеджеров пока нет.",reply_markup=admin_menu())
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b=InlineKeyboardBuilder(); text="👥 <b>Действующие менеджеры</b>\n\n"
    for u in ms:
        text+=f"• {quote(u.full_name)} · @{quote(u.username or 'без username')} · ID {u.telegram_id}\n"
        b.button(text=f"Снять права · {u.full_name[:18]}",callback_data=f"adm:remove:{u.telegram_id}")
    b.adjust(1); await message.answer(text,reply_markup=b.as_markup())
@router.message(F.text=="➕ Назначить менеджера")
async def add_manager(message,state,repo):
    if not await is_admin(message,repo): return
    await state.clear(); await state.set_state(ManagerForm.identifier); await message.answer("➕ <b>Назначение менеджера</b>\nВведите Telegram ID или @username пользователя. Пользователь должен хотя бы раз открыть бота.")
# explicit callback alternative because the previous helper cannot receive repo in filter
@router.message(ManagerForm.identifier)
async def manager_id(message,state,repo):
    if not await is_admin(message,repo):return
    value=(message.text or "").strip(); u=None
    if value.lstrip("+").isdigit():
        u=await repo.get_user(int(value))
    elif value.startswith("@") or value.isalnum(): u=await repo.find_user_by_username(value)
    if not u:return await message.answer("⚠️ Пользователь не найден. Пусть сначала отправит /start.")
    await state.update_data(telegram_id=u.telegram_id,full_name=u.full_name); await state.set_state(ManagerForm.confirm)
    await message.answer(f"Назначить менеджером?\n\n👤 {quote(u.full_name)}\n🆔 {u.telegram_id}\n👤 @{quote(u.username or 'нет')}")
@router.message(ManagerForm.confirm)
async def manager_confirm(message,state,repo):
    if not await is_admin(message,repo):return
    ans=(message.text or "").strip().lower(); d=await state.get_data()
    if ans not in {"да","нет"}:return await message.answer("Введите «да» или «нет».")
    if ans=="да": await repo.set_role(d["telegram_id"],Role.MANAGER.value); await message.answer("✅ Менеджер назначен.",reply_markup=admin_menu())
    else: await message.answer("❌ Отменено.",reply_markup=admin_menu())
    await state.clear()
@router.callback_query(F.data.startswith("adm:remove:"))
async def remove(call,repo):
    if not await is_admin(call,repo):return await call.answer("Нет доступа",show_alert=True)
    tid=int(call.data.split(":")[-1])
    if tid in settings.admin_id_set:return await call.answer("Главного администратора снять нельзя.",show_alert=True)
    ok=await repo.set_role(tid,Role.USER.value); await call.answer("Права сняты" if ok else "Пользователь не найден"); await show_managers(call.message,repo)
@router.message(F.text=="📁 Отчёт Excel")
async def report_start(message,state,repo):
    if not await is_admin(message,repo):return
    await state.clear(); await state.set_state(ReportForm.start_date); await message.answer("📁 Введите дату начала периода в формате YYYY-MM-DD.")
@router.message(ReportForm.start_date)
async def report_start_date(message,state):
    try:d=datetime.strptime((message.text or "").strip(),"%Y-%m-%d")
    except ValueError:return await message.answer("⚠️ Формат: YYYY-MM-DD")
    await state.update_data(start=d); await state.set_state(ReportForm.end_date); await message.answer("Введите конечную дату включительно в формате YYYY-MM-DD.")
@router.message(ReportForm.end_date)
async def report_end_date(message,state,repo):
    try:end=datetime.strptime((message.text or "").strip(),"%Y-%m-%d")+timedelta(days=1)
    except ValueError:return await message.answer("⚠️ Формат: YYYY-MM-DD")
    d=await state.get_data(); rows=await repo.all_orders(d["start"],end); f=build_report(rows); await state.clear(); await message.answer_document(BufferedInputFile(f.read(),filename="repair_report.xlsx"),caption=f"📁 Отчёт готов. Заявок: {len(rows)}",reply_markup=admin_menu())

@router.message(F.text=="👑 Администраторы")
async def administrators(message,repo):
    if not await is_admin(message,repo): return
    await show_administrators(message,repo)

async def show_administrators(message,repo,edit=False):
    admins=await repo.admins()
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b=InlineKeyboardBuilder()
    lines=["👑 <b>Администраторы</b>","",f"Всего: <b>{len(admins)}</b>",""]
    for u in admins:
        protected=u.telegram_id in settings.admin_id_set
        mark="⭐ Главный" if protected else "🛡 Администратор"
        lines.append(f"{mark} · {quote(u.full_name)}\nID: <code>{u.telegram_id}</code> · @{quote(u.username or 'без username')}")
        if not protected and u.telegram_id != message.from_user.id:
            b.button(text=f"❌ Снять права · {u.full_name[:18]}",callback_data=f"adm:remove_admin:{u.telegram_id}")
    b.button(text="➕ Добавить администратора",callback_data="adm:add_admin")
    b.button(text="⬅️ Системное меню",callback_data="adm:home")
    b.adjust(1)
    text="\n\n".join(lines)
    if edit: await message.edit_text(text,reply_markup=b.as_markup())
    else: await message.answer(text,reply_markup=b.as_markup())

@router.callback_query(F.data=="adm:add_admin")
async def add_admin_start(call,state,repo):
    if not await is_admin(call,repo): return await call.answer("Нет доступа",show_alert=True)
    await state.clear(); await state.set_state(AdminForm.identifier); await call.answer()
    await call.message.edit_text("➕ <b>Добавить администратора</b>\n\nВведите Telegram ID или @username пользователя. Он должен хотя бы раз открыть бота.\n\n/cancel — отмена")

@router.message(AdminForm.identifier)
async def add_admin_identifier(message,state,repo):
    if not await is_admin(message,repo): return
    value=(message.text or "").strip(); u=None
    if value.lstrip("+").isdigit(): u=await repo.get_user(int(value))
    else: u=await repo.find_user_by_username(value)
    if not u: return await message.answer("⚠️ Пользователь не найден. Пусть сначала отправит /start.")
    if u.role==Role.ADMIN.value: return await message.answer("ℹ️ Этот пользователь уже администратор.")
    await state.update_data(telegram_id=u.telegram_id,full_name=u.full_name)
    await state.set_state(AdminForm.confirm)
    await message.answer(f"👑 Назначить администратором?\n\n👤 {quote(u.full_name)}\n🆔 <code>{u.telegram_id}</code>\n👤 @{quote(u.username or 'нет')}\n\nНапишите: <b>да</b> или <b>нет</b>.")

@router.message(AdminForm.confirm)
async def add_admin_confirm(message,state,repo):
    if not await is_admin(message,repo): return
    ans=(message.text or "").strip().lower(); d=await state.get_data()
    if ans not in {"да","нет"}: return await message.answer("Введите «да» или «нет».")
    if ans=="да":
        ok=await repo.set_role(d["telegram_id"],Role.ADMIN.value)
        text="✅ Пользователь назначен администратором." if ok else "❌ Не удалось изменить роль."
    else: text="❌ Назначение отменено."
    await state.clear(); await message.answer(text,reply_markup=admin_menu())

@router.callback_query(F.data.startswith("adm:remove_admin:"))
async def remove_admin(call,repo):
    if not await is_admin(call,repo): return await call.answer("Нет доступа",show_alert=True)
    tid=int(call.data.split(":")[-1])
    if tid in settings.admin_id_set: return await call.answer("⭐ Главного администратора снять нельзя.",show_alert=True)
    if tid==call.from_user.id: return await call.answer("Нельзя снять права у самого себя.",show_alert=True)
    ok=await repo.set_role(tid,Role.USER.value)
    await call.answer("Права администратора сняты." if ok else "Пользователь не найден.")
    if ok: await show_administrators(call.message,repo,edit=True)

@router.message(F.text=="🚫 Пользователи")
async def users_control(message,repo):
    if not await is_admin(message,repo): return
    await show_users(message,repo,0)

@router.callback_query(F.data.startswith("adm:users:"))
async def users_page(call,repo):
    if not await is_admin(call,repo): return await call.answer("Нет доступа",show_alert=True)
    await call.answer(); await show_users(call.message,repo,int(call.data.split(":")[-1]),edit=True)

async def show_users(message,repo,page,edit=False):
    rows,total=await repo.users_page(page,8)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b=InlineKeyboardBuilder(); lines=["🚫 <b>Пользователи</b>",f"Страница {page+1} · всего {total}",""]
    for u in rows:
        role="👑 Админ" if u.role==Role.ADMIN.value else "🧑‍🔧 Менеджер" if u.role==Role.MANAGER.value else "👤 Пользователь"
        state="⛔ Заблокирован" if u.blocked else "🟢 Активен"
        lines.append(f"{role} · <b>{quote(u.full_name)}</b>\n👤 @{quote(u.username) if u.username else 'без username'}\n🆔 <code>{u.telegram_id}</code> · {state}")
        if u.role!=Role.ADMIN.value:
            label="🔓 Разблокировать" if u.blocked else "🚫 Заблокировать"
            b.button(text=f"{label} · {u.full_name[:16]}",callback_data=f"adm:block:{u.telegram_id}:{0 if u.blocked else 1}")
    if page>0:b.button(text="◀️",callback_data=f"adm:users:{page-1}")
    if (page+1)*8<total:b.button(text="▶️",callback_data=f"adm:users:{page+1}")
    b.button(text="⬅️ Системное меню",callback_data="adm:home"); b.adjust(1)
    text="\n\n".join(lines)
    if edit: await message.edit_text(text,reply_markup=b.as_markup())
    else: await message.answer(text,reply_markup=b.as_markup())

@router.callback_query(F.data.startswith("adm:block:"))
async def block_toggle(call,repo):
    if not await is_admin(call,repo): return await call.answer("Нет доступа",show_alert=True)
    _,_,tid,flag=call.data.split(":"); tid=int(tid); blocked=bool(int(flag))
    ok=await repo.set_blocked(tid,blocked)
    await call.answer("Пользователь заблокирован" if blocked and ok else "Пользователь разблокирован" if ok else "Нельзя изменить этого пользователя",show_alert=True)
    if ok: await show_users(call.message,repo,0,edit=True)
