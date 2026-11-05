"""
공용 FastAPI Dependency.
설계서 5.2 인증 구분 3가지 패턴(Public/Optional/Required) 대응.

- get_db: DB 세션
- get_current_user: Required Auth - 토큰 없거나 무효하면 401
- get_optional_user: Optional Auth - 토큰 없으면 None, 있으면 User 반환
- get_guest_session_id: 비로그인 사용자 식별용 UUID (헤더 없으면 신규 발급)
"""
import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, Header, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.config import settings
from app.core.exceptions import UnauthorizedException
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def _resolve_user_from_token(token: str | None, db: AsyncSession) -> User | None:
    if not token:
        return None
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None

    user_id = payload.get("sub")
    if user_id is None:
        return None

    result = await db.execute(select(User).where(User.id == int(user_id)))
    return result.scalar_one_or_none()


def _extract_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.split(" ")
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


async def get_current_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Required Auth. 토큰이 없거나 유효하지 않으면 401."""
    token = _extract_bearer_token(authorization)
    user = await _resolve_user_from_token(token, db)
    if user is None:
        raise UnauthorizedException(message="로그인이 필요한 기능입니다.")
    request.state.access_log_user_id = user.id
    return user


async def get_optional_user(
    request: Request,
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Optional Auth. 토큰이 없거나 유효하지 않으면 None (게스트로 처리)."""
    token = _extract_bearer_token(authorization)
    user = await _resolve_user_from_token(token, db)
    if user is not None:
        request.state.access_log_user_id = user.id
    return user


def get_guest_session_id(
    request: Request,
    response: Response,
) -> str:
    """
    비로그인 사용자 식별용 UUID.
    클라이언트가 X-Guest-Session-Id 헤더를 보내면 그대로 사용하고,
    없으면 신규 발급 후 응답 헤더로 내려준다 (설계서 5.3).

    TODO(구현 필요): 발급한 session_id를 쿠키로도 내려줄지 정책 결정
    (모바일 앱 클라이언트는 보통 로컬 저장소에 직접 보관하므로 헤더 방식이 더 적합할 수 있음)
    """
    header_name = settings.GUEST_SESSION_HEADER_NAME
    existing = request.headers.get(header_name)
    if existing:
        return existing

    new_session_id = str(uuid.uuid4())
    response.headers[header_name] = new_session_id
    return new_session_id
