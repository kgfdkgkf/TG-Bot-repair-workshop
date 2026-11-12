from datetime import datetime
from enum import Enum
from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase): pass
class Role(str, Enum): USER="user"; MANAGER="manager"; ADMIN="admin"
class OrderStatus(str, Enum):
    NEW="new"; ACCEPTED="accepted"; IN_PROGRESS="in_progress"; WAITING_PARTS="waiting_parts"; READY="ready"; COMPLETED="completed"; CANCELLED="cancelled"
STATUS_LABELS={"new":"🆕 Новая","accepted":"📥 Принята","in_progress":"🔧 В работе","waiting_parts":"⏳ Ожидает запчасть","ready":"✅ Готова","completed":"🏁 Завершена","cancelled":"❌ Отменена"}
class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    telegram_id: Mapped[int]=mapped_column(BigInteger,unique=True,index=True)
    username: Mapped[str|None]=mapped_column(String(255),nullable=True)
    full_name: Mapped[str]=mapped_column(String(255))
    role: Mapped[str]=mapped_column(String(20),default=Role.USER.value,index=True)
    blocked: Mapped[bool]=mapped_column(default=False,index=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
    orders: Mapped[list["Order"]]=relationship(back_populates="user", foreign_keys="Order.user_id")
    messages: Mapped[list["ChatMessage"]]=relationship(back_populates="user", foreign_keys="ChatMessage.user_id")
    manager_messages: Mapped[list["ChatMessage"]]=relationship(back_populates="manager", foreign_keys="ChatMessage.manager_id")
class Order(Base):
    __tablename__="orders"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    manager_id: Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    category: Mapped[str]=mapped_column(String(100))
    brand_model: Mapped[str]=mapped_column(String(255))
    problem: Mapped[str]=mapped_column(Text)
    cause: Mapped[str|None]=mapped_column(Text,nullable=True)
    condition: Mapped[str]=mapped_column(Text)
    phone: Mapped[str]=mapped_column(String(50))
    photo_file_id: Mapped[str|None]=mapped_column(String(500),nullable=True)
    status: Mapped[str]=mapped_column(String(30),default=OrderStatus.NEW.value,index=True)
    price: Mapped[int|None]=mapped_column(Integer,nullable=True)
    manager_comment: Mapped[str|None]=mapped_column(Text,nullable=True)
    created_at: Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
    updated_at: Mapped[datetime]=mapped_column(DateTime,server_default=func.now(),onupdate=func.now())
    user: Mapped[User]=relationship(back_populates="orders",foreign_keys=[user_id])
    manager: Mapped[User|None]=relationship(foreign_keys=[manager_id])
    messages: Mapped[list["ChatMessage"]]=relationship(back_populates="order",cascade="all, delete-orphan")
class ChatMessage(Base):
    __tablename__="chat_messages"
    id: Mapped[int]=mapped_column(Integer,primary_key=True)
    order_id: Mapped[int]=mapped_column(ForeignKey("orders.id",ondelete="CASCADE"),index=True)
    user_id: Mapped[int]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    manager_id: Mapped[int|None]=mapped_column(ForeignKey("users.id",ondelete="SET NULL"),nullable=True,index=True)
    sender_role: Mapped[str]=mapped_column(String(20),index=True)
    text: Mapped[str]=mapped_column(Text)
    created_at: Mapped[datetime]=mapped_column(DateTime,server_default=func.now())
    order: Mapped[Order]=relationship(back_populates="messages")
    user: Mapped[User]=relationship(back_populates="messages", foreign_keys=[user_id])
    manager: Mapped[User|None]=relationship(back_populates="manager_messages", foreign_keys=[manager_id])
