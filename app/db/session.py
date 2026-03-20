from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.core.config import settings
from app.db.base import Base

engine = create_async_engine(settings.database_url, future=True)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        result = await conn.execute(text("PRAGMA table_info(app_settings)"))
        columns = {row[1] for row in result.fetchall()}
        if "feishu_base_url" not in columns:
            await conn.execute(text("ALTER TABLE app_settings ADD COLUMN feishu_base_url VARCHAR(500)"))
