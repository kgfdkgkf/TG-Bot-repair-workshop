from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from app.config import settings
from app.db.models import Role
from app.db.repository import Repository
from app.states.forms import LoginForm
from app.keyboards.common import user_menu,manager_menu,admin_menu
router=Router()

def menu_for(role): return admin_menu() if role==Role.ADMIN.value else manager_menu() if role==Role.MANAGER.value else user_menu()
@router.message(Command("login"))
async def login_start(message: Message,state:FSMContext):
    await state.clear(); await state.set_state(LoginForm.password)
    await message.answer("🔐 <b>Вход сотрудника</b>\nВведите пароль.")
@router.message(LoginForm.password)
async def login_password(message: Message,state:FSMContext,repo:Repository):
    u=await repo.get_or_create_user(message.from_user.id,message.from_user.username,message.from_user.full_name)
    password=(message.text or "").strip()
    if password==settings.admin_password and message.from_user.id in settings.admin_id_set:
        await repo.set_role(u.telegram_id,Role.ADMIN.value); role=Role.ADMIN.value
    elif password==settings.manager_password and u.role==Role.MANAGER.value:
        role=Role.MANAGER.value
    else:
        await message.answer("❌ Неверный пароль или аккаунт не назначен менеджером."); return
    await state.clear(); await message.answer("✅ Вход выполнен.",reply_markup=menu_for(role))
