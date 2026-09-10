"""
Stock 관련 DB 접근 캡슐화.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_
from sqlalchemy.future import select

from app.models.stock import Stock


async def get_by_code(code: str, db: AsyncSession) -> Stock | None:
    result = await db.execute(select(Stock).where(Stock.code == code))
    return result.scalar_one_or_none()


async def search_by_name(query: str, db: AsyncSession, limit: int = 10) -> list[Stock]:
    result = await db.execute(
        select(Stock)
        .where(or_(Stock.name.contains(query), Stock.code.contains(query)))
        .limit(limit)
    )
    return list(result.scalars().all())
