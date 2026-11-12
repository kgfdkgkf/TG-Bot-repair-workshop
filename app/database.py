from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.db.models import Base

async def create_database(url: str):
    engine=create_async_engine(url,echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Небольшая совместимость со старыми БД: добавляем новое поле причины без потери данных.
        result=await conn.execute(text("PRAGMA table_info(orders)"))
        columns={row[1] for row in result.fetchall()}
        if "cause" not in columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN cause TEXT"))
        if "manager_id" not in columns:
            await conn.execute(text("ALTER TABLE orders ADD COLUMN manager_id INTEGER"))
        result=await conn.execute(text("PRAGMA table_info(users)"))
        user_columns={row[1] for row in result.fetchall()}
        if "blocked" not in user_columns:
            await conn.execute(text("ALTER TABLE users ADD COLUMN blocked BOOLEAN NOT NULL DEFAULT 0"))

        # Compatibility with older databases: ChatMessage.manager_id was added later.
        result=await conn.execute(text("PRAGMA table_info(chat_messages)"))
        chat_columns={row[1] for row in result.fetchall()}
        if "manager_id" not in chat_columns:
            await conn.execute(text("ALTER TABLE chat_messages ADD COLUMN manager_id INTEGER"))
    return engine,async_sessionmaker(engine,expire_on_commit=False)
