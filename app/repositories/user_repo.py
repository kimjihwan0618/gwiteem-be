"""
User 관련 DB 접근 캡슐화.
"""
from datetime import datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.user import User


async def get_by_provider(provider: str, provider_id: str, db: AsyncSession) -> User | None:
    result = await db.execute(
        select(User).where(User.provider == provider, User.provider_id == provider_id)
    )
    return result.scalar_one_or_none()


async def get_by_id(user_id: int, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_by_email(email: str, db: AsyncSession) -> User | None:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def create_local_user(
    email: str,
    password_hash: str,
    nickname: str,
    db: AsyncSession,
) -> User:
    user = User(
        provider="local",
        provider_id=email,
        email=email,
        nickname=nickname,
        password_hash=password_hash,
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    await db.flush()  # id 발급
    return user


async def create_user(
    provider: str,
    provider_id: str,
    nickname: str,
    email: str | None,
    profile_image_url: str | None,
    db: AsyncSession,
) -> User:
    user = User(
        provider=provider,
        provider_id=provider_id,
        nickname=nickname,
        email=email,
        profile_image_url=profile_image_url,
        last_login_at=datetime.utcnow(),
    )
    db.add(user)
    await db.flush()  # id 발급
    return user


async def update_last_login(user: User, db: AsyncSession) -> None:
    user.last_login_at = datetime.utcnow()
    db.add(user)


async def delete_user(user_id: int, db: AsyncSession) -> None:
    await db.execute(delete(User).where(User.id == user_id))
