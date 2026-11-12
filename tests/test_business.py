from app.db.models import STATUS_LABELS,OrderStatus

def test_statuses(): assert set(STATUS_LABELS)=={x.value for x in OrderStatus}
def test_role_menus_are_separate():
    from app.keyboards.common import user_menu,manager_menu,admin_menu
    assert user_menu().keyboard[0][0].text=="🛠 Создать заявку"
    assert manager_menu().keyboard[0][0].text=="📥 Новые заявки"
    assert admin_menu().keyboard[0][0].text=="📊 Дашборд"
