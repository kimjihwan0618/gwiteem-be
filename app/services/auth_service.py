"""
인증 비즈니스 로직.
"""
import secrets
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictException, InvalidRequestException, NotFoundException, UnauthorizedException
from app.core.redis import redis_client
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_strength,
    verify_password,
)
from app.external import oauth_client, ses_client
from app.models.user import User
from app.repositories import user_repo


_PROVIDER_LABELS = {"kakao": "카카오", "naver": "네이버", "google": "구글"}


def _provider_label(provider: str) -> str:
    return _PROVIDER_LABELS.get(provider, provider)


def _refresh_session_key(user_id: int, jti: str) -> str:
    """기기(세션) 단위 refresh token 키. 로그인 시 등록, 로그아웃/탈퇴 시 삭제."""
    return f"refresh_session:{user_id}:{jti}"


def _email_verification_code_key(email: str) -> str:
    """발송한 인증번호를 담아두는 키. TTL 만료 시 재발송 필요."""
    return f"email_verification_code:{email}"


def _email_verified_key(email: str) -> str:
    """인증번호 검증에 성공했음을 표시하는 키. register 시 확인 후 삭제한다."""
    return f"email_verified:{email}"


def _password_reset_code_key(email: str) -> str:
    """비밀번호 재설정용으로 발송한 인증번호 키. 회원가입 인증과는 별도 네임스페이스를 쓴다."""
    return f"password_reset_code:{email}"


def _password_reset_verified_key(email: str) -> str:
    """비밀번호 재설정 인증번호 검증에 성공했음을 표시하는 키. reset 시 확인 후 삭제한다."""
    return f"password_reset_verified:{email}"


async def send_email_verification_code(email: str, db: AsyncSession) -> None:
    """이메일로 6자리 인증번호를 발송하고 Redis에 TTL과 함께 저장한다."""
    existing = await user_repo.get_by_email(email, db)
    if existing is not None:
        if existing.provider != "local":
            label = _provider_label(existing.provider)
            raise ConflictException(
                message=f"이미 {label} 로그인으로 가입된 이메일입니다. {label} 로그인을 이용해주세요.",
                code="SOCIAL_ACCOUNT_EXISTS",
            )
        raise ConflictException(message="이미 가입된 이메일입니다.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    await redis_client.set(
        _email_verification_code_key(email),
        code,
        ex=timedelta(minutes=settings.EMAIL_VERIFICATION_CODE_TTL_MINUTES),
    )
    await ses_client.send_verification_email(email, code)


async def verify_email_code(email: str, code: str) -> None:
    """발송된 인증번호와 일치하는지 확인하고, 맞으면 인증 완료 상태로 표시한다."""
    stored_code = await redis_client.get(_email_verification_code_key(email))
    if stored_code is None or stored_code != code:
        raise InvalidRequestException(message="인증번호가 올바르지 않거나 만료되었습니다.", code="INVALID_VERIFICATION_CODE")

    await redis_client.delete(_email_verification_code_key(email))
    await redis_client.set(
        _email_verified_key(email),
        "1",
        ex=timedelta(minutes=settings.EMAIL_VERIFIED_TTL_MINUTES),
    )


async def send_password_reset_code(email: str, db: AsyncSession) -> None:
    """비밀번호 재설정용 인증번호를 발송한다. 이메일/비밀번호로 가입한 계정만 대상으로 한다."""
    user = await user_repo.get_by_email(email, db)
    if user is None or user.provider != "local":
        raise NotFoundException(message="가입된 이메일 계정을 찾을 수 없습니다.")

    code = f"{secrets.randbelow(1_000_000):06d}"
    await redis_client.set(
        _password_reset_code_key(email),
        code,
        ex=timedelta(minutes=settings.EMAIL_VERIFICATION_CODE_TTL_MINUTES),
    )
    await ses_client.send_password_reset_email(email, code)


async def verify_password_reset_code(email: str, code: str) -> None:
    """비밀번호 재설정 인증번호를 검증하고, 맞으면 새 비밀번호 입력 화면으로 넘어갈 수 있도록 표시한다."""
    stored_code = await redis_client.get(_password_reset_code_key(email))
    if stored_code is None or stored_code != code:
        raise InvalidRequestException(message="인증번호가 올바르지 않거나 만료되었습니다.", code="INVALID_VERIFICATION_CODE")

    await redis_client.delete(_password_reset_code_key(email))
    await redis_client.set(
        _password_reset_verified_key(email),
        "1",
        ex=timedelta(minutes=settings.EMAIL_VERIFIED_TTL_MINUTES),
    )


async def reset_password(email: str, new_password: str, db: AsyncSession) -> None:
    """인증번호 검증을 통과한 이메일에 한해 새 비밀번호로 재설정하고, 모든 기기의 로그인 세션을 무효화한다."""
    if await redis_client.get(_password_reset_verified_key(email)) is None:
        raise InvalidRequestException(message="이메일 인증이 필요합니다.", code="EMAIL_NOT_VERIFIED")

    validate_password_strength(new_password)

    user = await user_repo.get_by_email(email, db)
    if user is None or user.provider != "local":
        raise NotFoundException(message="가입된 이메일 계정을 찾을 수 없습니다.")

    user.password_hash = hash_password(new_password)
    db.add(user)
    await db.commit()

    await redis_client.delete(_password_reset_verified_key(email))
    async for key in redis_client.scan_iter(match=_refresh_session_key(user.id, "*")):
        await redis_client.delete(key)


async def register_local_user(
    email: str, password: str, nickname: str, db: AsyncSession
) -> tuple[User, bool]:
    """
    이메일/비밀번호 회원가입.
    Returns: (user, is_new_user) - OAuth 콜백과 동일한 반환 형태로 라우터에서 재사용.
    """
    nickname = nickname.strip()
    if not nickname:
        raise InvalidRequestException(
            message="닉네임을 입력해 주세요.", code="INVALID_NICKNAME"
        )
    if len(nickname) > 50:
        raise InvalidRequestException(
            message="닉네임은 50자 이하로 입력해 주세요.",
            code="INVALID_NICKNAME",
        )
    if await user_repo.get_by_nickname(nickname, db) is not None:
        raise ConflictException(
            message="이미 사용 중인 닉네임입니다.",
            code="NICKNAME_ALREADY_EXISTS",
        )

    existing = await user_repo.get_by_email(email, db)
    if existing is not None:
        if existing.provider != "local":
            label = _provider_label(existing.provider)
            raise ConflictException(
                message=f"이미 {label} 로그인으로 가입된 이메일입니다. {label} 로그인을 이용해주세요.",
                code="SOCIAL_ACCOUNT_EXISTS",
            )
        raise ConflictException(message="이미 가입된 이메일입니다.")

    if await redis_client.get(_email_verified_key(email)) is None:
        raise InvalidRequestException(message="이메일 인증이 필요합니다.", code="EMAIL_NOT_VERIFIED")

    validate_password_strength(password)

    user = await user_repo.create_local_user(
        email=email,
        password_hash=hash_password(password),
        nickname=nickname,
        db=db,
    )
    try:
        await db.commit()
    except IntegrityError:
        # 동시 요청으로 같은 이메일 또는 닉네임이 먼저 커밋된 경우
        await db.rollback()
        if await user_repo.get_by_nickname(nickname, db) is not None:
            raise ConflictException(
                message="이미 사용 중인 닉네임입니다.",
                code="NICKNAME_ALREADY_EXISTS",
            )
        raise ConflictException(message="이미 가입된 이메일입니다.")
    await db.refresh(user)
    await redis_client.delete(_email_verified_key(email))
    return user, True


async def is_nickname_available(nickname: str, db: AsyncSession) -> bool:
    """공백을 제거한 닉네임의 사용 가능 여부를 반환한다."""
    normalized = nickname.strip()
    if not normalized:
        raise InvalidRequestException(
            message="닉네임을 입력해 주세요.", code="INVALID_NICKNAME"
        )
    if len(normalized) > 50:
        raise InvalidRequestException(
            message="닉네임은 50자 이하로 입력해 주세요.",
            code="INVALID_NICKNAME",
        )
    return await user_repo.get_by_nickname(normalized, db) is None


async def make_available_nickname(nickname: str, db: AsyncSession) -> str:
    """소셜 로그인 닉네임이 중복되면 숫자 접미사를 붙인다."""
    base = nickname.strip()[:50] or "사용자"
    if await user_repo.get_by_nickname(base, db) is None:
        return base

    suffix = 2
    while True:
        suffix_text = f"-{suffix}"
        candidate = f"{base[: 50 - len(suffix_text)]}{suffix_text}"
        if await user_repo.get_by_nickname(candidate, db) is None:
            return candidate
        suffix += 1


async def login_local_user(email: str, password: str, db: AsyncSession) -> User:
    """이메일/비밀번호 로그인."""
    user = await user_repo.get_by_email(email, db)
    if user is None:
        raise UnauthorizedException(message="이메일 또는 비밀번호가 올바르지 않습니다.", code="INVALID_CREDENTIALS")

    if user.password_hash is None:
        # OAuth로 가입해 비밀번호가 없는 계정. 소셜 로그인 안내.
        label = _provider_label(user.provider)
        raise UnauthorizedException(
            message=f"{label} 로그인으로 가입된 계정입니다. {label} 로그인을 이용해주세요.",
            code="SOCIAL_LOGIN_REQUIRED",
        )

    if not verify_password(password, user.password_hash):
        raise UnauthorizedException(message="이메일 또는 비밀번호가 올바르지 않습니다.", code="INVALID_CREDENTIALS")

    await user_repo.update_last_login(user, db)
    await db.commit()
    await db.refresh(user)
    return user


async def handle_oauth_callback(
    provider: str, code: str, state: str | None, db: AsyncSession
) -> tuple[User, bool]:
    """
    소셜 로그인 콜백 처리.
    Returns: (user, is_new_user)
    """
    access_token = await oauth_client.exchange_code_for_token(provider, code, state)
    info = await oauth_client.fetch_user_info(provider, access_token)
    user = await user_repo.get_by_provider(provider, info["provider_id"], db)

    # 이미 다른 로그인 방식으로 가입했더라도 OAuth 제공자가 확인한 동일 이메일이면
    # 기존 계정으로 연결해 users.email 고유 제약으로 인한 500 오류를 방지한다.
    if user is None and info.get("email"):
        user = await user_repo.get_by_email(info["email"], db)

    if user is None:
        nickname = await make_available_nickname(info["nickname"], db)
        user = await user_repo.create_user(
            provider=provider,
            provider_id=info["provider_id"],
            nickname=nickname,
            email=info.get("email"),
            profile_image_url=info.get("profile_image_url"),
            db=db,
        )
        is_new_user = True
        try:
            await db.commit()
        except IntegrityError:
            # 동시 콜백 요청으로 같은 소셜 계정이 먼저 커밋된 경우 (check-then-insert race)
            # 신규 가입이 아니라 로그인으로 취급하고 기존 유저를 재조회한다.
            await db.rollback()
            user = await user_repo.get_by_provider(provider, info["provider_id"], db)
            if user is None:
                raise
            await user_repo.update_last_login(user, db)
            await db.commit()
            is_new_user = False
    else:
        await user_repo.update_last_login(user, db)
        is_new_user = False
        await db.commit()

    await db.refresh(user)
    return user, is_new_user


async def withdraw_user(user_id: int, db: AsyncSession) -> None:
    """회원 탈퇴. FK cascade로 선택 이력도 삭제하고 모든 기기의 로그인 세션을 무효화한다."""
    await user_repo.delete_user(user_id, db)
    await db.commit()

    async for key in redis_client.scan_iter(match=_refresh_session_key(user_id, "*")):
        await redis_client.delete(key)


async def issue_tokens(user: User) -> dict:
    """access_token + refresh_token 발급. refresh_token은 기기(세션) 단위로 Redis에 등록한다."""
    access_token = create_access_token(user.id)
    refresh_token, jti = create_refresh_token(user.id)

    await redis_client.set(
        _refresh_session_key(user.id, jti),
        "1",
        ex=timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "Bearer",
        "expires_in": settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
    }


async def verify_refresh_session(user_id: int, jti: str) -> bool:
    """refresh token의 세션이 아직 Redis에 살아있는지 확인 (로그아웃/탈퇴 시 삭제됨)."""
    return await redis_client.exists(_refresh_session_key(user_id, jti)) == 1


async def logout(user_id: int, refresh_token: str) -> None:
    """로그아웃. 요청한 기기(refresh_token)의 세션만 무효화하고 다른 기기 세션은 유지한다."""
    payload = decode_token(refresh_token)
    if not payload or payload.get("type") != "refresh" or int(payload.get("sub", -1)) != user_id:
        raise UnauthorizedException(message="유효하지 않은 refresh token입니다.", code="INVALID_REFRESH_TOKEN")

    jti = payload.get("jti")
    if jti:
        await redis_client.delete(_refresh_session_key(user_id, jti))
