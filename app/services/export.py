from io import BytesIO
from openpyxl import Workbook
from app.db.models import STATUS_LABELS

def build_report(orders):
    wb=Workbook(); ws=wb.active; ws.title="Заявки"
    ws.append(["ID","Telegram ID","Пользователь","Username","Менеджер","Менеджер Username","Категория","Модель","Проблема","Причина","Состояние","Телефон","Статус","Цена","Комментарий","Создана"])
    for o in orders:
        u=o.user
        m=o.manager
        ws.append([o.id,u.telegram_id,u.full_name,u.username or "",m.full_name if m else "",m.username if m else "",o.category,o.brand_model,o.problem,o.cause,o.condition,o.phone,STATUS_LABELS.get(o.status,o.status),o.price,o.manager_comment,o.created_at.strftime("%Y-%m-%d %H:%M") if o.created_at else ""])
    for col in ws.columns:
        letter=col[0].column_letter; ws.column_dimensions[letter].width=min(45,max(12,max(len(str(x.value or "")) for x in col)+2))
    out=BytesIO(); wb.save(out); out.seek(0); return out
