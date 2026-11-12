from datetime import datetime
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload
from .models import Order, OrderStatus, Role, User

class Repository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def get_or_create_user(self, telegram_id: int, username: str | None, full_name: str) -> User:
        async with self.session_factory() as s:
            u = await s.scalar(select(User).where(User.telegram_id == telegram_id))
            if u:
                u.username, u.full_name = username, full_name
                await s.commit()
                return u
            u = User(telegram_id=telegram_id, username=username, full_name=full_name)
            s.add(u); await s.commit(); await s.refresh(u); return u

    async def get_user(self, telegram_id: int) -> User | None:
        async with self.session_factory() as s:
            return await s.scalar(select(User).where(User.telegram_id == telegram_id))

    async def get_user_by_id(self, user_id: int) -> User | None:
        async with self.session_factory() as s:
            return await s.scalar(select(User).where(User.id == user_id))

    async def find_user_by_username(self, username: str) -> User | None:
        username = username.lstrip("@").strip().lower()
        async with self.session_factory() as s:
            return await s.scalar(select(User).where(func.lower(User.username) == username))


    async def users_page(self, page: int = 0, per_page: int = 10):
        async with self.session_factory() as s:
            total=int(await s.scalar(select(func.count(User.id))) or 0)
            rows=list(await s.scalars(select(User).order_by(User.id.desc()).offset(page*per_page).limit(per_page)))
            return rows,total

    async def set_blocked(self, telegram_id: int, blocked: bool) -> bool:
        async with self.session_factory() as s:
            u=await s.scalar(select(User).where(User.telegram_id==telegram_id))
            if not u or u.role==Role.ADMIN.value: return False
            u.blocked=blocked
            await s.commit()
            return True

    async def set_role(self, telegram_id: int, role: str) -> bool:
        async with self.session_factory() as s:
            u = await s.scalar(select(User).where(User.telegram_id == telegram_id))
            if not u: return False
            u.role = role; await s.commit(); return True

    async def create_order(self, user_id: int, data: dict) -> Order:
        async with self.session_factory() as s:
            o = Order(user_id=user_id, **data); s.add(o); await s.commit()
            await s.refresh(o); return o

    async def get_order(self, order_id: int) -> Order | None:
        async with self.session_factory() as s:
            return await s.scalar(select(Order).options(selectinload(Order.user), selectinload(Order.manager)).where(Order.id == order_id))

    async def user_orders(self, telegram_id: int, page: int = 0, per_page: int = 5) -> tuple[list[Order], int]:
        # Явно указываем FK user_id: у Order есть ещё manager_id -> User,
        # поэтому обычный join(User) приводит к AmbiguousForeignKeysError.
        async with self.session_factory() as s:
            join_condition = Order.user_id == User.id
            qbase = (
                select(Order)
                .join(User, join_condition)
                .options(selectinload(Order.user), selectinload(Order.manager))
                .where(User.telegram_id == telegram_id)
            )
            total_q = (
                select(func.count(Order.id))
                .select_from(Order)
                .join(User, join_condition)
                .where(User.telegram_id == telegram_id)
            )
            total = int(await s.scalar(total_q) or 0)
            rows = list(await s.scalars(qbase.order_by(Order.id.desc()).offset(page*per_page).limit(per_page)))
            return rows, total

    async def manager_orders(self, status: str | None = None, page: int = 0, per_page: int = 3) -> tuple[list[Order], int]:
        async with self.session_factory() as s:
            q = select(Order).options(selectinload(Order.user), selectinload(Order.manager)).order_by(Order.id.desc())
            c = select(func.count(Order.id))
            if status:
                q, c = q.where(Order.status == status), c.where(Order.status == status)
            total = int(await s.scalar(c) or 0)
            return list(await s.scalars(q.offset(page*per_page).limit(per_page))), total

    async def assign_manager(self, order_id: int, manager_id: int) -> bool:
        async with self.session_factory() as s:
            o=await s.scalar(select(Order).where(Order.id==order_id))
            m=await s.scalar(select(User).where(User.id==manager_id, User.role.in_([Role.MANAGER.value, Role.ADMIN.value])))
            if not o or not m: return False
            o.manager_id=manager_id
            await s.commit()
            return True

    async def update_status(self, order_id: int, status: str, manager_id: int | None = None) -> tuple[bool, Order | None, str | None]:
        # Статусы идут только вперёд. Терминальные состояния нельзя вернуть назад.
        allowed = {
            OrderStatus.NEW.value: {OrderStatus.ACCEPTED.value, OrderStatus.CANCELLED.value},
            OrderStatus.ACCEPTED.value: {OrderStatus.IN_PROGRESS.value, OrderStatus.CANCELLED.value},
            OrderStatus.IN_PROGRESS.value: {OrderStatus.WAITING_PARTS.value, OrderStatus.READY.value, OrderStatus.CANCELLED.value},
            OrderStatus.WAITING_PARTS.value: {OrderStatus.IN_PROGRESS.value, OrderStatus.READY.value, OrderStatus.CANCELLED.value},
            OrderStatus.READY.value: {OrderStatus.COMPLETED.value},
            OrderStatus.COMPLETED.value: set(),
            OrderStatus.CANCELLED.value: set(),
        }
        async with self.session_factory() as s:
            o = await s.scalar(select(Order).options(selectinload(Order.user), selectinload(Order.manager)).where(Order.id == order_id))
            if not o: return False, None, None
            old = o.status
            if old == status: return False, o, old
            if status not in allowed.get(old, set()):
                return False, o, old
            o.status = status
            if manager_id and status not in {OrderStatus.NEW.value, OrderStatus.CANCELLED.value}:
                o.manager_id = manager_id
            await s.commit()
            await s.refresh(o)
            return True, o, old

    async def set_price(self, order_id: int, price: int, comment: str | None, manager_id: int | None = None) -> tuple[bool, Order | None, int | None]:
        async with self.session_factory() as s:
            o = await s.scalar(select(Order).options(selectinload(Order.user), selectinload(Order.manager)).where(Order.id == order_id))
            if not o: return False, None, None
            old = o.price
            changed = old != price
            o.price, o.manager_comment = price, comment
            if manager_id:
                o.manager_id = manager_id
            await s.commit(); await s.refresh(o); return changed, o, old

    async def stats(self) -> dict:
        async with self.session_factory() as s:
            users = int(await s.scalar(select(func.count(User.id))) or 0)
            orders = int(await s.scalar(select(func.count(Order.id))) or 0)
            new = int(await s.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.NEW.value)) or 0)
            active = int(await s.scalar(select(func.count(Order.id)).where(Order.status.in_([OrderStatus.ACCEPTED.value, OrderStatus.IN_PROGRESS.value, OrderStatus.WAITING_PARTS.value, OrderStatus.READY.value]))) or 0)
            completed = int(await s.scalar(select(func.count(Order.id)).where(Order.status == OrderStatus.COMPLETED.value)) or 0)
            revenue = int(await s.scalar(select(func.coalesce(func.sum(Order.price), 0)).where(Order.status == OrderStatus.COMPLETED.value)) or 0)
            return {"users": users, "orders": orders, "new": new, "active": active, "completed": completed, "revenue": revenue}

    async def all_orders(self, start: datetime | None = None, end: datetime | None = None) -> list[Order]:
        async with self.session_factory() as s:
            q = select(Order).options(selectinload(Order.user), selectinload(Order.manager)).order_by(Order.id)
            if start: q = q.where(Order.created_at >= start)
            if end: q = q.where(Order.created_at < end)
            return list(await s.scalars(q))

    async def manager_stats(self) -> list[tuple[User, int, int, int]]:
        async with self.session_factory() as s:
            managers = list(await s.scalars(select(User).where(User.role == Role.MANAGER.value).order_by(User.full_name)))
            result=[]
            for m in managers:
                total=int(await s.scalar(select(func.count(Order.id)).where(Order.manager_id==m.id)) or 0)
                active=int(await s.scalar(select(func.count(Order.id)).where(Order.manager_id==m.id, Order.status.in_([OrderStatus.ACCEPTED.value, OrderStatus.IN_PROGRESS.value, OrderStatus.WAITING_PARTS.value, OrderStatus.READY.value]))) or 0)
                done=int(await s.scalar(select(func.count(Order.id)).where(Order.manager_id==m.id, Order.status==OrderStatus.COMPLETED.value)) or 0)
                result.append((m,total,active,done))
            return result

    async def admins(self) -> list[User]:
        async with self.session_factory() as s:
            return list(await s.scalars(select(User).where(User.role == Role.ADMIN.value).order_by(User.full_name)))

    async def managers(self) -> list[User]:
        async with self.session_factory() as s:
            return list(await s.scalars(select(User).where(User.role == Role.MANAGER.value).order_by(User.full_name)))

    async def add_chat_message(self, order_id: int, sender_id: int, sender_role: str, text_value: str):
        from .models import ChatMessage
        async with self.session_factory() as s:
            msg=ChatMessage(order_id=order_id,user_id=sender_id,manager_id=sender_id if sender_role==Role.MANAGER.value else None,sender_role=sender_role,text=text_value)
            s.add(msg); await s.commit(); await s.refresh(msg); return msg

    async def chat_messages(self, order_id: int, limit: int = 30):
        from .models import ChatMessage
        async with self.session_factory() as s:
            q=select(ChatMessage).options(selectinload(ChatMessage.user)).where(ChatMessage.order_id==order_id).order_by(ChatMessage.id.desc()).limit(limit)
            return list(reversed((await s.scalars(q)).all()))
