from sqlalchemy.exc import IntegrityError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.settings import AppSettings


async def get_or_create_settings(session: AsyncSession) -> AppSettings:
    result = await session.execute(select(AppSettings).where(AppSettings.id == 1))
    settings = result.scalar_one_or_none()
    if settings is not None:
        return settings

    settings = AppSettings(id=1)
    session.add(settings)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        result = await session.execute(select(AppSettings).where(AppSettings.id == 1))
        settings = result.scalar_one()
        return settings

    await session.refresh(settings)
    return settings


async def update_settings(session: AsyncSession, values: dict) -> AppSettings:
    settings = await get_or_create_settings(session)

    for key, value in values.items():
        setattr(settings, key, value)

    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    return settings
