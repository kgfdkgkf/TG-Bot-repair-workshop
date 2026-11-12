from app.db.models import Role

# Temporary interface mode for administrators. The real role in DB stays ADMIN.
_admin_modes: dict[int, str] = {}

def get_mode(telegram_id: int, db_role: str) -> str:
    if db_role == Role.ADMIN.value:
        return _admin_modes.get(telegram_id, Role.ADMIN.value)
    return db_role

def set_mode(telegram_id: int, role: str) -> None:
    if role not in {Role.ADMIN.value, Role.MANAGER.value, Role.USER.value}:
        raise ValueError("Unknown role")
    _admin_modes[telegram_id] = role

def clear_mode(telegram_id: int) -> None:
    _admin_modes.pop(telegram_id, None)
