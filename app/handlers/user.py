import re
from aiogram import F, Router, html
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardMarkup, KeyboardButton
from app.db.models import STATUS_LABELS, Role
from app.db.repository import Repository
from app.keyboards.common import user_menu,wizard_nav,confirm_kb,device_kb,problem_kb,cause_kb,condition_kb,phone_kb,user_orders_kb,user_order_actions,chat_kb,component_kb,pc_problem_kb
from app.services.catalog import DEVICE_CATALOG, COMMON_CONDITIONS
from app.services.computer_catalog import PC_COMPONENTS
from app.states.forms import RepairForm, UserChatForm
router=Router()

async def is_user_mode(obj, repo):
    from app.services.access import effective_role
    return (await effective_role(obj, repo)) == Role.USER.value
PHONE_RE=re.compile(r"^(?:\+7|7)\d{10}$")

def quote(v): return html.quote(str(v))
def prompt(step,text,total=8): return f"<b>Шаг {step}/{total}</b>\n{text}"
def valid_phone(v): return bool(PHONE_RE.fullmatch(v))
KNOWN_BRANDS={"apple","iphone","samsung","xiaomi","redmi","poco","huawei","honor","google","pixel","oneplus","oppo","vivo","nokia","motorola","sony","lg","asus","acer","lenovo","hp","dell","msi","gigabyte","huawei","macbook","mac","playstation","xbox","nintendo","jbl","bose","airpods","realme","tecno","infinix"}

def sane_text(v, min_len=2, max_len=255):
    v=v.strip()
    if not min_len<=len(v)<=max_len or not re.search(r"[\wА-Яа-яЁё]",v): return False
    if len(set(v.lower().replace(' ','')))<2: return False
    letters=re.findall(r"[А-Яа-яЁёA-Za-z]",v)
    if letters and not re.search(r"[аеёиоуыэюяaeiou]", ''.join(letters).lower()) and not re.search(r"\d",v): return False
    return True

def valid_model(v):
    if not sane_text(v,2,255): return False
    low=v.lower()
    if re.search(r"\d",v): return True
    return any(b in low for b in KNOWN_BRANDS) or len(v.split())>=2

def valid_free(v,min_len,max_len):
    if not sane_text(v,min_len,max_len): return False
    words=v.split()
    return len(words)>=2 or len(v)>=15

async def start_form(message,state):
    await state.clear(); await state.set_state(RepairForm.category)
    await message.answer("🛠 <b>Новая заявка</b>\n\nВыберите тип техники. Дальше бот будет показывать только подходящие варианты неисправностей.",reply_markup=device_kb())

@router.message(F.text=="🛠 Создать заявку")
async def create_text(message,state): await start_form(message,state)
@router.callback_query(F.data=="user:create")
async def create_cb(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Переключите режим на пользователя", show_alert=True)
    await call.answer(); await start_form(call.message,state)

@router.callback_query(F.data.startswith("repair:device:"))
async def choose_device(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    value=call.data.split(":",2)[2]
    if value=="custom":
        await state.set_state(RepairForm.category); await call.answer(); return await call.message.answer("✏️ Напишите название устройства. Не используйте случайный набор букв.",reply_markup=wizard_nav())
    if value not in DEVICE_CATALOG: return await call.answer("Неизвестное устройство",show_alert=True)
    await call.answer(); await state.update_data(category=value); await state.set_state(RepairForm.brand_model)
    if value=="🖥 Компьютер":
        text="<b>Шаг 2/8</b>\nДля сборного ПК не нужно придумывать модель. Укажите конфигурацию: например <i>Ryzen 5, RTX 3060, 16 ГБ RAM, SSD 1 ТБ</i>."
    else: text=prompt(2,"Укажите бренд и модель устройства.")
    await call.message.edit_text(text+f"\n\nВы выбрали: <b>{quote(value)}</b>",reply_markup=wizard_nav("repair:back:device"))

@router.message(RepairForm.category)
async def custom_device(message,state):
    text=(message.text or "").strip()
    if not sane_text(text,2,100): return await message.answer("⚠️ Не похоже на название устройства. Напишите, например: электронная книга.")
    await state.update_data(category=text); await state.set_state(RepairForm.brand_model); await message.answer(prompt(2,"Напишите бренд и модель / описание устройства."),reply_markup=wizard_nav("repair:back:device"))

@router.callback_query(F.data=="repair:back:device")
async def back_device(call,state,repo):
    if not await is_user_mode(call,repo):
        return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    await state.set_state(RepairForm.category)
    await call.answer()
    await call.message.edit_text("🛠 <b>Выберите устройство</b>", reply_markup=device_kb())

@router.message(RepairForm.brand_model)
async def brand(message,state):
    text=(message.text or "").strip()
    if not valid_model(text): return await message.answer("⚠️ Укажите реальную модель/конфигурацию. Например: iPhone 15 Pro, Samsung Galaxy S24, MacBook Air.")
    data=await state.get_data(); device=data.get("category"); await state.update_data(brand_model=text)
    if device=="🖥 Компьютер":
        await state.set_state(RepairForm.component); return await message.answer(prompt(3,"Что именно неисправно? Для сборного ПК выберите комплектующее или узел."),reply_markup=component_kb())
    await state.set_state(RepairForm.problem)
    if device in DEVICE_CATALOG: return await message.answer(prompt(3,f"Выберите неисправность для <b>{quote(device)}</b>."),reply_markup=problem_kb(device))
    await message.answer(prompt(3,"Опишите неисправность своими словами (не случайный набор букв)."),reply_markup=wizard_nav("repair:back:device"))

@router.callback_query(F.data.startswith("repair:component:"))
async def choose_component(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    value=call.data.split(":",2)[2]; await call.answer()
    if value=="custom":
        await state.set_state(RepairForm.component); return await call.message.answer("✏️ Напишите комплектующее/узел: например, блок питания, корпус или охлаждение.",reply_markup=wizard_nav("repair:back:device"))
    if not value.isdigit() or int(value)>=len(PC_COMPONENTS): return await call.answer("Комплектующее не найдено",show_alert=True)
    component=list(PC_COMPONENTS)[int(value)]; await state.update_data(component=component); await state.set_state(RepairForm.problem)
    await call.message.edit_text(prompt(4,f"Выберите неисправность для <b>{quote(component)}</b>."),reply_markup=pc_problem_kb(component))

@router.message(RepairForm.component)
async def custom_component(message,state):
    text=(message.text or "").strip()
    if not sane_text(text,3,120): return await message.answer("⚠️ Укажите понятное название комплектующего.")
    await state.update_data(component=text); await state.set_state(RepairForm.problem); await message.answer(prompt(4,"Опишите неисправность комплектующего (минимум 10 символов)."),reply_markup=wizard_nav("repair:back:component"))

@router.callback_query(F.data=="repair:back:component")
async def back_component(call,state,repo):
    if not await is_user_mode(call,repo):
        return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    await state.set_state(RepairForm.component)
    await call.answer()
    await call.message.edit_text(prompt(3,"Выберите комплектующее или узел компьютера."),reply_markup=component_kb())

@router.callback_query(F.data.startswith("repair:pcproblem:"))
async def choose_pc_problem(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    value=call.data.split(":",2)[2]; data=await state.get_data(); component=data.get("component"); await call.answer()
    if value=="custom":
        await state.set_state(RepairForm.problem); return await call.message.answer("✏️ Опишите неисправность (10–2000 символов).",reply_markup=wizard_nav("repair:back:component"))
    if component not in PC_COMPONENTS or not value.isdigit(): return await call.answer("Не удалось определить неисправность",show_alert=True)
    problems=list(PC_COMPONENTS[component]); idx=int(value)
    if idx>=len(problems): return await call.answer("Неисправность не найдена",show_alert=True)
    problem=problems[idx]; await state.update_data(problem=problem); await state.set_state(RepairForm.cause)
    await call.message.edit_text(prompt(5,f"Выберите причину для <b>{quote(problem)}</b>."),reply_markup=cause_kb_from_pc(component,problem))

def cause_kb_from_pc(component,problem):
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b=InlineKeyboardBuilder()
    for i,c in enumerate(PC_COMPONENTS[component][problem]): b.button(text=c,callback_data=f"repair:pccause:{i}")
    b.button(text="✏️ Другая причина",callback_data="repair:pccause:custom"); b.button(text="⬅️ К неисправностям",callback_data="repair:back:pcproblem"); b.button(text="❌ Отмена",callback_data="wizard:cancel"); b.adjust(1); return b.as_markup()

@router.callback_query(F.data=="repair:back:pcproblem")
async def back_pcproblem(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    data=await state.get_data(); component=data.get("component"); await state.set_state(RepairForm.problem); await call.answer()
    if component in PC_COMPONENTS: return await call.message.edit_text(prompt(4,"Выберите неисправность."),reply_markup=pc_problem_kb(component))
    await call.message.edit_text(prompt(4,"Опишите неисправность."),reply_markup=wizard_nav("repair:back:component"))

@router.callback_query(F.data.startswith("repair:pccause:"))
async def choose_pc_cause(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    value=call.data.split(":",2)[2]; data=await state.get_data(); component=data.get("component"); problem=data.get("problem"); await call.answer()
    if value=="custom": await state.set_state(RepairForm.cause); return await call.message.answer("✏️ Опишите причину (3–1000 символов).",reply_markup=wizard_nav("repair:back:pcproblem"))
    if component not in PC_COMPONENTS or problem not in PC_COMPONENTS[component] or not value.isdigit(): return await call.answer("Причина не соответствует неисправности",show_alert=True)
    causes=PC_COMPONENTS[component][problem]; idx=int(value)
    if idx>=len(causes): return await call.answer("Причина не найдена",show_alert=True)
    await state.update_data(cause=causes[idx]); await state.set_state(RepairForm.condition); await call.message.edit_text(prompt(6,"В каком состоянии техника?"),reply_markup=condition_kb())

@router.callback_query(F.data.startswith("repair:problem:"))
async def choose_problem(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    data=await state.get_data(); device=data.get("category"); value=call.data.split(":",2)[2]; await call.answer()
    if value=="custom": await state.set_state(RepairForm.problem); return await call.message.answer("✏️ Опишите неисправность (10–2000 символов).",reply_markup=wizard_nav("repair:back:device"))
    if device not in DEVICE_CATALOG or not value.isdigit(): return await call.answer("Не удалось определить проблему",show_alert=True)
    problems=list(DEVICE_CATALOG[device]); idx=int(value)
    if idx>=len(problems): return await call.answer("Проблема не найдена",show_alert=True)
    problem=problems[idx]; await state.update_data(problem=problem); await state.set_state(RepairForm.cause); await call.message.edit_text(prompt(4,f"Выберите причину именно для <b>{quote(problem)}</b>."),reply_markup=cause_kb(device,problem))

@router.message(RepairForm.problem)
async def custom_problem(message,state):
    text=(message.text or "").strip()
    if not valid_free(text,10,2000): return await message.answer("⚠️ Опишите проблему нормальным предложением, минимум 10 символов. Случайный набор букв не принимается.")
    await state.update_data(problem=text,cause="Причина описана клиентом"); await state.set_state(RepairForm.condition); await message.answer(prompt(6,"В каком состоянии техника?"),reply_markup=condition_kb())

@router.callback_query(F.data.startswith("repair:cause:"))
async def choose_cause(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    data=await state.get_data(); device=data.get("category"); problem=data.get("problem"); value=call.data.split(":",2)[2]; await call.answer()
    if value=="custom": await state.set_state(RepairForm.cause); return await call.message.answer("✏️ Опишите причину (3–1000 символов).",reply_markup=wizard_nav("repair:back:problem"))
    if device not in DEVICE_CATALOG or problem not in DEVICE_CATALOG[device] or not value.isdigit(): return await call.answer("Причина не соответствует выбранной проблеме",show_alert=True)
    causes=DEVICE_CATALOG[device][problem]; idx=int(value)
    if idx>=len(causes): return await call.answer("Причина не найдена",show_alert=True)
    await state.update_data(cause=causes[idx]); await state.set_state(RepairForm.condition); await call.message.edit_text(prompt(6,"В каком состоянии техника?"),reply_markup=condition_kb())

@router.message(RepairForm.cause)
async def custom_cause(message,state):
    text=(message.text or "").strip()
    if not valid_free(text,3,1000): return await message.answer("⚠️ Опишите причину понятно. Случайный набор букв не принимается.")
    await state.update_data(cause=text); await state.set_state(RepairForm.condition); await message.answer(prompt(6,"В каком состоянии техника?"),reply_markup=condition_kb())

@router.callback_query(F.data=="repair:back:problem")
async def back_problem(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    data=await state.get_data(); device=data.get("category"); await state.set_state(RepairForm.problem); await call.answer()
    if device in DEVICE_CATALOG:return await call.message.edit_text(prompt(3,"Выберите неисправность."),reply_markup=problem_kb(device))
    await call.message.edit_text(prompt(3,"Опишите неисправность."),reply_markup=wizard_nav("repair:back:device"))

@router.callback_query(F.data.startswith("repair:condition:"))
async def choose_condition(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    value=call.data.split(":",2)[2]; await call.answer()
    if value=="custom": await state.set_state(RepairForm.condition); return await call.message.answer("✏️ Опишите состояние техники (3–1000 символов).",reply_markup=wizard_nav("repair:back:cause"))
    if not value.isdigit() or int(value)>=len(COMMON_CONDITIONS): return await call.answer("Неизвестный вариант",show_alert=True)
    await state.update_data(condition=COMMON_CONDITIONS[int(value)]); await state.set_state(RepairForm.phone); await call.message.edit_text(prompt(7,"Введите номер строго в формате <b>7XXXXXXXXXX</b> или <b>+7XXXXXXXXXX</b>."),reply_markup=phone_kb())

@router.message(RepairForm.condition)
async def custom_condition(message,state):
    text=(message.text or "").strip()
    if not valid_free(text,3,1000): return await message.answer("⚠️ Опишите состояние техники понятными словами.")
    await state.update_data(condition=text); await state.set_state(RepairForm.phone); await message.answer(prompt(7,"Введите номер строго в формате 7XXXXXXXXXX или +7XXXXXXXXXX."),reply_markup=phone_kb())

@router.callback_query(F.data=="repair:back:cause")
async def back_cause(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    data=await state.get_data(); device=data.get("category"); problem=data.get("problem"); component=data.get("component"); await state.set_state(RepairForm.cause); await call.answer()
    if component in PC_COMPONENTS and problem in PC_COMPONENTS[component]: return await call.message.edit_text(prompt(5,f"Выберите причину для <b>{quote(problem)}</b>."),reply_markup=cause_kb_from_pc(component,problem))
    if device in DEVICE_CATALOG and problem in DEVICE_CATALOG[device]: return await call.message.edit_text(prompt(4,f"Выберите причину для <b>{quote(problem)}</b>."),reply_markup=cause_kb(device,problem))
    await call.message.edit_text(prompt(5,"Опишите причину."),reply_markup=wizard_nav("repair:back:problem"))

@router.callback_query(F.data=="repair:phone:contact")
async def phone_contact(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    await call.answer(); await call.message.answer("📱 Нажмите кнопку ниже — Telegram передаст номер автоматически.",reply_markup=ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="📞 Отправить номер",request_contact=True)]],resize_keyboard=True,one_time_keyboard=True))

@router.message(RepairForm.phone,F.contact)
async def phone_contact_received(message,state):
    raw=message.contact.phone_number.strip().replace(" ","").replace("-","").replace("(","").replace(")","")
    normalized=raw if raw.startswith(("7","+7")) else ""
    if not valid_phone(normalized): return await message.answer("⚠️ Номер не принят. Нужен только формат 7XXXXXXXXXX или +7XXXXXXXXXX.")
    await state.update_data(phone=normalized); await state.set_state(RepairForm.photo); await message.answer(prompt(8,"Пришлите <b>фото техники</b>. Одно фото обязательно."),reply_markup=wizard_nav("repair:back:phone"))

@router.message(RepairForm.phone)
async def phone(message,state):
    text=(message.text or "").strip()
    if not valid_phone(text): return await message.answer("⚠️ Неверный номер. Разрешены только 7XXXXXXXXXX или +7XXXXXXXXXX — без пробелов, скобок и дефисов.")
    await state.update_data(phone=text); await state.set_state(RepairForm.photo); await message.answer(prompt(8,"Пришлите <b>фото техники</b>. Одно фото обязательно."),reply_markup=wizard_nav("repair:back:phone"))

@router.callback_query(F.data=="repair:back:phone")
async def back_phone(call,state,repo):
    if not await is_user_mode(call,repo):
        return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    await state.set_state(RepairForm.phone)
    await call.answer()
    await call.message.edit_text(prompt(7,"Введите номер строго в формате 7XXXXXXXXXX или +7XXXXXXXXXX."),reply_markup=phone_kb())

@router.message(RepairForm.photo,F.photo)
async def photo(message,state):
    await state.update_data(photo_file_id=message.photo[-1].file_id); await state.set_state(RepairForm.confirm); d=await state.get_data(); await message.answer("📋 <b>Проверьте заявку</b>\n\n"+summary(d),reply_markup=confirm_kb())
@router.message(RepairForm.photo)
async def wrong_photo(message): await message.answer("⚠️ Сейчас нужен именно снимок техники. Отправьте фото, а не текст/файл другого типа.")

@router.callback_query(F.data=="wizard:confirm")
async def confirm(call,state,repo:Repository):
    if not await is_user_mode(call,repo): return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    u=await repo.get_or_create_user(call.from_user.id,call.from_user.username,call.from_user.full_name); d=await state.get_data()
    required=["category","brand_model","problem","cause","condition","phone","photo_file_id"]
    if any(k not in d for k in required): return await call.answer("Заявка заполнена не полностью",show_alert=True)
    o=await repo.create_order(u.id,{k:d[k] for k in required}); await state.clear(); await call.answer("Заявка создана!")
    await call.message.edit_text(f"🎉 <b>Заявка #{o.id} создана</b>\n\nМенеджер уже получил её. Следить за ремонтом можно в разделе «Мои заявки». ")
    await call.message.answer("Главное меню",reply_markup=user_menu())

@router.callback_query(F.data=="wizard:edit")
async def edit(call,state,repo):
    if not await is_user_mode(call,repo):
        return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    await state.clear()
    await state.set_state(RepairForm.category)
    await call.answer()
    await call.message.edit_text("🛠 <b>Заполните заявку заново</b>",reply_markup=device_kb())
@router.callback_query(F.data=="wizard:cancel")
async def cancel(call,state,repo):
    if not await is_user_mode(call,repo):
        return await call.answer("Нет доступа в текущем режиме", show_alert=True)
    await state.clear()
    await call.answer("Отменено")
    await call.message.edit_text("❌ Создание заявки отменено.")
    await call.message.answer("Главное меню",reply_markup=user_menu())

@router.message(F.text=="📋 Мои заявки")
async def my_orders(message,repo): await show_my_orders(message,repo,0)
@router.callback_query(F.data.startswith("user:list:"))
async def my_orders_page(call,repo):
    if not await is_user_mode(call,repo):
        return await call.answer("Переключите режим на пользователя", show_alert=True)
    raw=call.data.rsplit(":",1)[-1]
    if not raw.isdigit(): return await call.answer("Страница не найдена", show_alert=True)
    await call.answer()
    await show_my_orders(call.message,repo,int(raw),edit=True)
async def show_my_orders(message,repo,page,edit=False):
    rows,total=await repo.user_orders(message.chat.id,page,5); text="📋 <b>Мои заявки</b>\n\n"; markup=user_orders_kb(rows,page,total) if rows else None; text += "Выберите заявку, чтобы открыть подробности." if rows else "Заявок пока нет. Нажмите «🛠 Создать заявку»."
    if edit: await message.edit_text(text,reply_markup=markup)
    else: await message.answer(text,reply_markup=markup)

@router.callback_query(F.data.startswith("user:order:"))
async def user_order_detail(call,repo):
    if not await is_user_mode(call,repo): return await call.answer("Переключите режим на пользователя", show_alert=True)
    oid=int(call.data.split(":")[-1]); o=await repo.get_order(oid)
    if not o or o.user.telegram_id!=call.from_user.id:return await call.answer("Заявка не найдена",show_alert=True)
    manager_line = (f"🧑‍🔧 <b>Менеджер:</b> {quote(o.manager.full_name)}" + (f" · @{quote(o.manager.username)}" if o.manager.username else "")) if o.manager else "🧑‍🔧 <b>Менеджер:</b> ещё не назначен"
    await call.answer(); text=(f"📋 <b>Заявка #{o.id}</b>\n\n📱 <b>Устройство:</b> {quote(o.category)}\n🏷 <b>Модель / конфигурация:</b> {quote(o.brand_model)}\n🛠 <b>Проблема:</b> {quote(o.problem)}\n🔎 <b>Причина:</b> {quote(o.cause or 'Не указана')}\n📦 <b>Состояние:</b> {quote(o.condition)}\n☎️ <b>Телефон:</b> {quote(o.phone)}\n{manager_line}\n\n📌 <b>Статус:</b> {STATUS_LABELS.get(o.status,o.status)}\n💰 <b>Цена:</b> {o.price if o.price is not None else 'не указана'} ₽\n💬 <b>Комментарий:</b> {quote(o.manager_comment) if o.manager_comment else '—'}")
    await call.message.edit_text(text,reply_markup=user_order_actions(o.id,o.status in {"new","accepted"}))
    if o.photo_file_id: await call.message.answer_photo(o.photo_file_id,caption=f"📷 Фото заявки #{o.id}")

@router.callback_query(F.data.startswith("user:cancel:"))
async def cancel_order(call,repo):
    if not await is_user_mode(call,repo): return await call.answer("Переключите режим на пользователя", show_alert=True)
    oid=int(call.data.split(":")[-1]); o=await repo.get_order(oid)
    if not o or o.user.telegram_id!=call.from_user.id:return await call.answer("Заявка не найдена",show_alert=True)
    if o.status not in {"new","accepted"}:return await call.answer("Эту заявку уже нельзя отменить",show_alert=True)
    changed,_,_=await repo.update_status(oid,"cancelled"); await call.answer("Заявка отменена" if changed else "Статус уже изменён"); await call.message.edit_text(f"❌ <b>Заявка #{oid} отменена.</b>"); await call.message.answer("Главное меню",reply_markup=user_menu())

@router.message(F.text=="🧾 История ремонтов")
async def history(message,repo):
    rows,total=await repo.user_orders(message.chat.id,0,50); completed=[o for o in rows if o.status=="completed"]
    if not completed:return await message.answer("🧾 <b>История ремонтов</b>\n\nЗавершённых ремонтов пока нет.",reply_markup=user_menu())
    await message.answer("🧾 <b>История ремонтов</b>\n\n"+"\n\n".join(f"🏁 <b>#{o.id}</b> · {quote(o.brand_model)}\n🛠 {quote(o.problem)}\n💰 {o.price if o.price is not None else 'Цена не указана'} ₽" for o in completed),reply_markup=user_menu())

@router.message(F.text=="👤 Мой профиль")
async def profile(message,repo):
    u=await repo.get_user(message.from_user.id); _,total=await repo.user_orders(message.chat.id,0,1)
    await message.answer(f"👤 <b>Мой профиль</b>\n\nИмя: {quote(u.full_name)}\nUsername: @{quote(u.username or 'не указан')}\n🧾 Всего заявок: <b>{total}</b>",reply_markup=user_menu())

@router.message(F.text=="🧰 Услуги")
async def services(message): await message.answer("🧰 <b>Ремонтируем</b>\n\n"+"\n".join(f"{d} — {len(p)} типовых неисправностей" for d,p in DEVICE_CATALOG.items()),reply_markup=user_menu())
@router.message(F.text=="❓ FAQ")
async def faq(message): await message.answer("❓ <b>FAQ</b>\n\n<b>Как получить цену?</b> Менеджер пришлёт её в чат заявки.\n\n<b>Можно ли отменить заявку?</b> Да, пока она новая или принята.\n\n<b>Зачем фото?</b> Оно помогает менеджеру быстрее понять состояние техники.",reply_markup=user_menu())
@router.message(F.text=="💡 Советы")
async def tips(message): await message.answer("💡 <b>Перед ремонтом</b>\n\n• Сделайте несколько фото повреждений.\n• Если техника включается — сохраните важные данные.\n• Для залитой техники не подключайте питание повторно.\n• Чем точнее описание симптомов, тем быстрее диагностика.\n\n✨ После отправки заявки просто следите за статусом и чатом.",reply_markup=user_menu())
@router.message(F.text=="📞 Помощь")
async def help_user(message): await message.answer("📞 <b>Помощь</b>\n\nСоздайте заявку, приложите фото и общайтесь с менеджером в отдельном чате заявки.",reply_markup=user_menu())

@router.message(F.text=="💬 Мои чаты")
async def my_chats(message,repo):
    rows,total=await repo.user_orders(message.chat.id,0,50); rows=[o for o in rows if o.status!="cancelled"]
    if not rows:return await message.answer("💬 <b>Мои чаты</b>\n\nПока нет заявок, по которым можно открыть чат.",reply_markup=user_menu())
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    b=InlineKeyboardBuilder()
    for o in rows:b.button(text=f"💬 Заявка #{o.id} · {o.brand_model[:22]}",callback_data=f"chat:user:{o.id}")
    b.adjust(1); await message.answer("💬 <b>Чаты с менеджерами</b>\n\nВыберите заявку:",reply_markup=b.as_markup())

@router.callback_query(F.data == "chat:user:back")
async def user_chat_back(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Переключите режим на пользователя", show_alert=True)
    # Этот callback должен обрабатываться ДО chat:user:<id>, иначе "back"
    # пытается преобразоваться в int и вызывает внутреннюю ошибку.
    await state.clear()
    await call.answer()
    await call.message.answer("🏠 Главное меню", reply_markup=user_menu())

@router.callback_query(F.data.startswith("chat:user:"))
async def user_chat_open(call,state,repo):
    if not await is_user_mode(call,repo): return await call.answer("Переключите режим на пользователя", show_alert=True)
    raw_id = call.data.rsplit(":", 1)[-1]
    if not raw_id.isdigit():
        return await call.answer("Чат не найден", show_alert=True)
    oid = int(raw_id)
    o = await repo.get_order(oid)
    if not o or not o.user or o.user.telegram_id != call.from_user.id:
        return await call.answer("Чат не найден", show_alert=True)
    await state.clear()
    await state.update_data(chat_order_id=oid, chat_role="user")
    await state.set_state(UserChatForm.text)
    await call.answer()
    await show_chat(call.message, repo, o, edit=True)
    await call.message.answer("✍️ Напишите сообщение. Оно привязано только к этой заявке.\n\n/cancel — закрыть чат")

@router.message(UserChatForm.text)
async def chat_send(message,state,repo):
    d=await state.get_data(); oid=d.get("chat_order_id"); role=d.get("chat_role"); text=(message.text or "").strip()
    if role!="user": return
    if not oid:return await state.clear()
    if not 1<=len(text)<=2000:return await message.answer("⚠️ Сообщение от 1 до 2000 символов.")
    o=await repo.get_order(oid)
    if not o or o.user.telegram_id!=message.from_user.id:return await state.clear()
    u=await repo.get_user(message.from_user.id); await repo.add_chat_message(oid,u.id,Role.USER.value,text)
    managers=await repo.managers(); sent=0; body=f"💬 <b>Новое сообщение по заявке #{oid}</b>\n\n👤 {quote(message.from_user.full_name)}\n\n{quote(text)}\n\nОткройте заявку, чтобы ответить клиенту."
    for m in managers:
        try: await message.bot.send_message(m.telegram_id,body); sent+=1
        except Exception: pass
    await message.answer("✅ Сообщение отправлено менеджерам." if sent else "⚠️ Менеджеры недоступны. Сообщение сохранено в чате.")
    await show_chat(message,repo,o)

def summary(d):
    extra=f"\n🧩 <b>Комплектующее:</b> {quote(d['component'])}" if d.get('component') else ""
    return f"📱 <b>Устройство:</b> {quote(d['category'])}{extra}\n🏷 <b>Модель / конфигурация:</b> {quote(d['brand_model'])}\n🛠 <b>Проблема:</b> {quote(d['problem'])}\n🔎 <b>Причина:</b> {quote(d.get('cause','Не указана'))}\n📦 <b>Состояние:</b> {quote(d['condition'])}\n☎️ <b>Телефон:</b> {quote(d['phone'])}\n📷 <b>Фото:</b> прикреплено"

async def show_chat(message,repo,o,edit=False):
    msgs=await repo.chat_messages(o.id,30); lines=[f"💬 <b>Чат по заявке #{o.id}</b>",f"📱 {quote(o.brand_model)} · {STATUS_LABELS.get(o.status,o.status)}"," "]
    if not msgs: lines.append("Сообщений пока нет. Напишите первое сообщение ниже.")
    for m in msgs:
        who="👤 Клиент" if m.sender_role==Role.USER.value else "🧑‍🔧 Менеджер"; lines.append(f"<b>{who}</b> · {m.created_at:%d.%m %H:%M}\n{quote(m.text)}")
    markup=chat_kb(o.id,"chat:user:back")
    if edit: await message.edit_text("\n\n".join(lines),reply_markup=markup)
    else: await message.answer("\n\n".join(lines),reply_markup=markup)
