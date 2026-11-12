from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
router=Router()
@router.message()
async def fallback(message:Message,state:FSMContext):
    # Не перехватываем активные FSM: специализированный state-handler должен дать внятную валидацию.
    if await state.get_state(): return
    await message.answer("Не понял сообщение. Используйте кнопки меню или /start.")
