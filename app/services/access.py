from app.config import settings
from app.db.models import Role
from app.services.mode import get_mode
async def current_user(obj, repo):
    return await repo.get_user(obj.from_user.id)
async def require_role(obj, repo, role):
    u=await current_user(obj,repo)
    return bool(u and u.role==role)
async def ensure_base_user(obj, repo):
    return await repo.get_or_create_user(obj.from_user.id,obj.from_user.username,obj.from_user.full_name)


async def effective_role(obj, repo):
    u = await current_user(obj, repo)
    return get_mode(obj.from_user.id, u.role) if u else None
