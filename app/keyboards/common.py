from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.db.models import STATUS_LABELS
from app.services.catalog import DEVICE_CATALOG, COMMON_CONDITIONS
from app.services.computer_catalog import PC_COMPONENTS

def user_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🛠 Создать заявку"), KeyboardButton(text="📋 Мои заявки")],
        [KeyboardButton(text="💬 Мои чаты"), KeyboardButton(text="🧾 История ремонтов")],
        [KeyboardButton(text="👤 Мой профиль"), KeyboardButton(text="🧰 Услуги")],
        [KeyboardButton(text="❓ FAQ"), KeyboardButton(text="💡 Советы")],
        [KeyboardButton(text="📞 Помощь")],
    ], resize_keyboard=True, input_field_placeholder="Выберите действие…")

def manager_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📥 Новые заявки"), KeyboardButton(text="🔧 В работе")],
        [KeyboardButton(text="📋 Все заявки"), KeyboardButton(text="💬 Чаты")],
        [KeyboardButton(text="🏁 Завершённые"), KeyboardButton(text="📈 Сводка дня")],
        [KeyboardButton(text="🔄 Обновить")],
    ], resize_keyboard=True, input_field_placeholder="Панель менеджера")

def admin_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📊 Дашборд"), KeyboardButton(text="🔎 Заявки")],
        [KeyboardButton(text="📁 Отчёт Excel"), KeyboardButton(text="👥 Менеджеры")],
        [KeyboardButton(text="🚫 Пользователи"), KeyboardButton(text="👑 Администраторы")],
        [KeyboardButton(text="📈 Работа менеджеров"), KeyboardButton(text="➕ Назначить менеджера")],
        [KeyboardButton(text="🔄 Режим")],
    ], resize_keyboard=True, input_field_placeholder="Системная панель")

def wizard_nav(back_data=None):
    b=InlineKeyboardBuilder()
    if back_data: b.button(text="⬅️ Назад",callback_data=back_data)
    b.button(text="❌ Отмена",callback_data="wizard:cancel"); b.adjust(2); return b.as_markup()

def device_kb():
    b=InlineKeyboardBuilder()
    for name in DEVICE_CATALOG: b.button(text=name,callback_data=f"repair:device:{name}")
    b.button(text="➕ Другое устройство",callback_data="repair:device:custom")
    b.button(text="❌ Отмена",callback_data="wizard:cancel"); b.adjust(2); return b.as_markup()

def component_kb():
    b=InlineKeyboardBuilder()
    for name in PC_COMPONENTS: b.button(text=name,callback_data=f"repair:component:{list(PC_COMPONENTS).index(name)}")
    b.button(text="➕ Другое / не знаю",callback_data="repair:component:custom")
    b.button(text="⬅️ К устройствам",callback_data="repair:back:device"); b.button(text="❌ Отмена",callback_data="wizard:cancel")
    b.adjust(1); return b.as_markup()

def pc_problem_kb(component):
    b=InlineKeyboardBuilder(); problems=list(PC_COMPONENTS[component])
    for idx,p in enumerate(problems): b.button(text=p,callback_data=f"repair:pcproblem:{idx}")
    b.button(text="✏️ Другая проблема",callback_data="repair:pcproblem:custom")
    b.button(text="⬅️ К комплектующим",callback_data="repair:back:component"); b.button(text="❌ Отмена",callback_data="wizard:cancel")
    b.adjust(1); return b.as_markup()

def problem_kb(device):
    b=InlineKeyboardBuilder()
    for idx,problem in enumerate(DEVICE_CATALOG[device]): b.button(text=problem,callback_data=f"repair:problem:{idx}")
    b.button(text="✏️ Другая проблема",callback_data="repair:problem:custom")
    b.button(text="⬅️ К устройствам",callback_data="repair:back:device"); b.button(text="❌ Отмена",callback_data="wizard:cancel")
    b.adjust(1); return b.as_markup()

def cause_kb(device,problem):
    b=InlineKeyboardBuilder()
    for idx,cause in enumerate(DEVICE_CATALOG[device][problem]): b.button(text=cause,callback_data=f"repair:cause:{idx}")
    b.button(text="✏️ Другая причина",callback_data="repair:cause:custom")
    b.button(text="⬅️ К проблемам",callback_data="repair:back:problem"); b.button(text="❌ Отмена",callback_data="wizard:cancel")
    b.adjust(1); return b.as_markup()

def condition_kb():
    b=InlineKeyboardBuilder()
    for idx,value in enumerate(COMMON_CONDITIONS): b.button(text=value,callback_data=f"repair:condition:{idx}")
    b.button(text="✏️ Опишу сам",callback_data="repair:condition:custom"); b.button(text="⬅️ Назад",callback_data="repair:back:cause"); b.button(text="❌ Отмена",callback_data="wizard:cancel")
    b.adjust(1); return b.as_markup()

def phone_kb():
    b=InlineKeyboardBuilder(); b.button(text="📱 Отправить мой номер",callback_data="repair:phone:contact"); b.button(text="⬅️ Назад",callback_data="repair:back:condition"); b.button(text="❌ Отмена",callback_data="wizard:cancel"); b.adjust(1); return b.as_markup()

def confirm_kb():
    b=InlineKeyboardBuilder(); b.button(text="✅ Отправить заявку",callback_data="wizard:confirm"); b.button(text="✏️ Заполнить заново",callback_data="wizard:edit"); b.button(text="❌ Отмена",callback_data="wizard:cancel"); b.adjust(1); return b.as_markup()

def manager_orders_kb(orders,page,total,status=None):
    b=InlineKeyboardBuilder()
    for o in orders: b.button(text=f"#{o.id} · {o.brand_model[:28]}",callback_data=f"mgr:order:{o.id}")
    if page>0:b.button(text="◀️ Назад",callback_data=f"mgr:list:{page-1}:{status or 'all'}")
    if (page+1)*3<total:b.button(text="Вперёд ▶️",callback_data=f"mgr:list:{page+1}:{status or 'all'}")
    b.button(text="🏠 Главное меню",callback_data="nav:home")
    b.adjust(1); return b.as_markup()

def order_actions(order_id,status):
    b=InlineKeyboardBuilder()
    transitions = {
        "new": [("accepted","📥 Принять"),("cancelled","❌ Отменить")],
        "accepted": [("in_progress","🔧 В работу"),("cancelled","❌ Отменить")],
        "in_progress": [("waiting_parts","⏳ Запчасть"),("ready","✅ Готова"),("cancelled","❌ Отменить")],
        "waiting_parts": [("in_progress","🔧 Вернуть в работу"),("ready","✅ Готова"),("cancelled","❌ Отменить")],
        "ready": [("completed","🏁 Завершить")],
        "completed": [],
        "cancelled": [],
    }
    for code,label in transitions.get(status,[]):
        b.button(text=label,callback_data=f"mgr:status:{order_id}:{code}")
    if status not in {"completed","cancelled"}:
        b.button(text="💰 Указать цену",callback_data=f"mgr:price:{order_id}")
        b.button(text="💬 Чат с клиентом",callback_data=f"chat:mgr:{order_id}")
    else:
        b.button(text="💬 История чата",callback_data=f"chat:mgr:{order_id}")
    b.button(text="⬅️ К списку",callback_data=f"mgr:list:0:{status}")
    b.adjust(2,2,1,1,1)
    return b.as_markup()

def chat_kb(order_id, back):
    b = InlineKeyboardBuilder()
    b.button(text="⬅️ Назад", callback_data=back)
    b.button(text="🏠 Главное меню", callback_data="nav:home")
    b.adjust(1)
    return b.as_markup()

def admin_status_kb():
    b=InlineKeyboardBuilder(); b.button(text="Все",callback_data="adm:orders:all:0")
    for s,l in STATUS_LABELS.items(): b.button(text=l,callback_data=f"adm:orders:{s}:0")
    b.button(text="⬅️ Системное меню",callback_data="adm:home"); b.adjust(2); return b.as_markup()

def admin_orders_page_kb(status,page,total,orders=None):
    b=InlineKeyboardBuilder()
    for o in (orders or []):
        b.button(text=f"📋 #{o.id} · {o.brand_model[:24]}",callback_data=f"adm:order:{o.id}")
    if page>0:b.button(text="◀️",callback_data=f"adm:orders:{status}:{page-1}")
    if (page+1)*5<total:b.button(text="▶️",callback_data=f"adm:orders:{status}:{page+1}")
    b.button(text="🔎 Фильтр",callback_data="adm:order_filter")
    b.button(text="🏠 Системное меню",callback_data="adm:home")
    b.adjust(2,1); return b.as_markup()

def user_orders_kb(orders,page,total):
    b=InlineKeyboardBuilder()
    for o in orders:b.button(text=f"#{o.id} · {o.brand_model[:26]}",callback_data=f"user:order:{o.id}")
    if page>0:b.button(text="◀️",callback_data=f"user:list:{page-1}")
    if (page+1)*5<total:b.button(text="▶️",callback_data=f"user:list:{page+1}")
    b.button(text="🏠 Главное меню",callback_data="nav:home")
    b.adjust(1); return b.as_markup()

def user_order_actions(order_id,can_cancel=True):
    b=InlineKeyboardBuilder()
    b.button(text="💬 Открыть чат",callback_data=f"chat:user:{order_id}")
    if can_cancel:b.button(text="❌ Отменить заявку",callback_data=f"user:cancel:{order_id}")
    b.button(text="⬅️ Мои заявки",callback_data="user:list:0"); b.adjust(1); return b.as_markup()
