from aiogram.fsm.state import State, StatesGroup
class RepairForm(StatesGroup):
    category=State(); brand_model=State(); component=State(); problem=State(); cause=State(); condition=State(); phone=State(); photo=State(); confirm=State()
class LoginForm(StatesGroup): password=State()
class PriceForm(StatesGroup): price=State(); comment=State()
class MessageForm(StatesGroup): text=State()
class UserMessageForm(StatesGroup): text=State()
class UserChatForm(StatesGroup): text=State()
class ManagerChatForm(StatesGroup): text=State()
class ManagerForm(StatesGroup): identifier=State(); confirm=State()
class AdminForm(StatesGroup): identifier=State(); confirm=State()
class ReportForm(StatesGroup): start_date=State(); end_date=State()
