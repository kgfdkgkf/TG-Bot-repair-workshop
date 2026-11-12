from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from app.config import settings
from app.db.models import Role
from app.db.repository import Repository
from app.keyboards.common import user_menu,manager_menu,admin_menu
from app.services.mode import get_mode, set_mode, clear_mode
router=Router()
@router.message(Command(commands=["cancel", "canel"]))
async def cancel_anywhere(message: Message, state, repo):
    current = await state.get_state()
    if not current:
        await message.answer("ℹ️ Сейчас нет активной команды, которую нужно отменять.")
        return
    await state.clear()
    u = await repo.get_user(message.from_user.id)
    if not u:
        await message.answer("❌ Команда отменена. Отправьте /start.")
        return
    mode = get_mode(message.from_user.id, u.role)
    menu = admin_menu() if mode == Role.ADMIN.value else manager_menu() if mode == Role.MANAGER.value else user_menu()
    await message.answer("❌ Текущее действие отменено. Вы вернулись в главное меню.", reply_markup=menu)

@router.callback_query(F.data == "nav:home")
async def home_callback(call, state, repo):
    await state.clear()
    u = await repo.get_user(call.from_user.id)
    if not u:
        await call.answer("Сначала отправьте /start", show_alert=True)
        return
    mode = get_mode(call.from_user.id, u.role)
    menu = admin_menu() if mode == Role.ADMIN.value else manager_menu() if mode == Role.MANAGER.value else user_menu()
    await call.answer()
    await call.message.answer("🏠 Главное меню", reply_markup=menu)

@router.message(Command("admin"))
async def admin_mode(message: Message, repo: Repository):
    u=await repo.get_user(message.from_user.id)
    if not u or u.role!=Role.ADMIN.value:
        await message.answer("⛔ Доступно только администраторам.")
        return
    clear_mode(message.from_user.id)
    set_mode(message.from_user.id,Role.ADMIN.value)
    await message.answer("⚙️ Вы вернулись в режим администратора.",reply_markup=admin_menu())

@router.callback_query(F.data=="nav:admin")
async def nav_admin(call,repo):
    u=await repo.get_user(call.from_user.id)
    if not u or u.role!=Role.ADMIN.value:
        return await call.answer("Нет доступа",show_alert=True)
    set_mode(call.from_user.id,Role.ADMIN.value); await call.answer(); await call.message.answer("⚙️ Админ-панель",reply_markup=admin_menu())

@router.message(F.text=="🔄 Режим")
async def mode_menu(message,repo):
    u=await repo.get_user(message.from_user.id)
    if not u or u.role!=Role.ADMIN.value:return
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b=InlineKeyboardBuilder()
    b.button(text="👑 Администратор",callback_data="admin:mode:admin")
    b.button(text="🧑‍🔧 Менеджер",callback_data="admin:mode:manager")
    b.button(text="👤 Пользователь",callback_data="admin:mode:user")
    b.adjust(1)
    await message.answer("🔄 <b>Режим работы</b>\n\nВыберите, какой интерфейс открыть. Ваша админская роль и права сохраняются.",reply_markup=b.as_markup())

@router.callback_query(F.data.startswith("admin:mode:"))
async def set_admin_mode(call,state,repo):
    u=await repo.get_user(call.from_user.id)
    if not u or u.role!=Role.ADMIN.value:return await call.answer("Нет доступа",show_alert=True)
    role=call.data.split(":")[-1]
    mapping={"admin":Role.ADMIN.value,"manager":Role.MANAGER.value,"user":Role.USER.value}
    if role not in mapping:return await call.answer("Неизвестный режим",show_alert=True)
    await state.clear()
    set_mode(call.from_user.id,mapping[role]); await call.answer("Режим изменён")
    menu=admin_menu() if role=="admin" else manager_menu() if role=="manager" else user_menu()
    text={"admin":"⚙️ Режим администратора","manager":"🧑‍🔧 Режим менеджера","user":"👤 Режим пользователя"}[role]
    await call.message.answer(text+"\n\nДля возврата в админ-панель используйте /admin.",reply_markup=menu)

@router.message(CommandStart())
async def start(message:Message,repo:Repository):
    u=await repo.get_or_create_user(message.from_user.id,message.from_user.username,message.from_user.full_name)
    if message.from_user.id in settings.admin_id_set and u.role!=Role.ADMIN.value:
        await repo.set_role(u.telegram_id,Role.ADMIN.value); u.role=Role.ADMIN.value
    mode=get_mode(message.from_user.id,u.role)
    menu=admin_menu() if mode==Role.ADMIN.value else manager_menu() if mode==Role.MANAGER.value else user_menu()
    title="🛠 <b>Сервис ремонта</b>" if mode==Role.USER.value else "🧰 <b>Панель менеджера</b>" if mode==Role.MANAGER.value else "⚙️ <b>Системная панель администратора</b>"
    if mode==Role.USER.value:
        text=("✨ <b>Добро пожаловать в мастерскую у CYхарика!</b>\n\n"
              "Здесь можно быстро оставить заявку на ремонт, следить за её статусом и общаться с менеджером.\n\n"
              "🔧 Выберите действие в меню ниже — всё лишнее скрыто.")
    else:
        text=f"{title}\n\nВыберите нужное действие ниже."
    await message.answer(text,reply_markup=menu)
