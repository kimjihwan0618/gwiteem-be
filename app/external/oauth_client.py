"""
소셜 로그인(카카오/네이버/구글) OAuth 클라이언트.
"""
import logging
from urllib.parse import urlencode

import httpx

from app.core.config import settings
from app.core.exceptions import InvalidRequestException

SUPPORTED_PROVIDERS = {"naver", "google"}  # TODO(구현 필요): kakao email 미제공 이슈 해결 후 재활성화
logger = logging.getLogger(__name__)


def _assert_provider(provider: str) -> None:
    if provider not in SUPPORTED_PROVIDERS:
        raise InvalidRequestException(f"지원하지 않는 provider입니다: {provider}")


def build_authorize_url(provider: str) -> str:
    """provider별 OAuth authorize URL 반환."""
    _assert_provider(provider)

    # TODO(구현 필요): kakao email 미제공 이슈 해결 전까지 비활성화 (SUPPORTED_PROVIDERS에서도 제외됨)
    # if provider == "kakao":
    #     return (
    #         "https://kauth.kakao.com/oauth/authorize"
    #         f"?client_id={settings.KAKAO_CLIENT_ID}"
    #         f"&redirect_uri={settings.KAKAO_REDIRECT_URI}"
    #         "&response_type=code"
    #     )
    if provider == "naver":
        return "https://nid.naver.com/oauth2.0/authorize?" + urlencode(
            {
                "response_type": "code",
                "client_id": settings.NAVER_CLIENT_ID,
                "redirect_uri": settings.NAVER_REDIRECT_URI,
                "state": "gwiteem",
            }
        )
    # google
    return (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={settings.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={settings.GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid email profile"
    )


async def exchange_code_for_token(provider: str, code: str, state: str | None) -> str:
    """provider에 code를 넘겨 OAuth access_token을 교환해 반환."""
    _assert_provider(provider)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
        # TODO(구현 필요): kakao email 미제공 이슈 해결 전까지 비활성화 (SUPPORTED_PROVIDERS에서도 제외됨)
        # if provider == "kakao":
        #     resp = await client.post(
        #         "https://kauth.kakao.com/oauth/token",
        #         data={
        #             "grant_type": "authorization_code",
        #             "client_id": settings.KAKAO_CLIENT_ID,
        #             "client_secret": settings.KAKAO_CLIENT_SECRET,
        #             "redirect_uri": settings.KAKAO_REDIRECT_URI,
        #             "code": code,
        #         },
        #     )
            if provider == "naver":
                if not state:
                    raise InvalidRequestException(
                        message="네이버 로그인 state 값이 없습니다.",
                        code="OAUTH_STATE_MISSING",
                    )
                resp = await client.get(
                    "https://nid.naver.com/oauth2.0/token",
                    params={
                        "grant_type": "authorization_code",
                        "client_id": settings.NAVER_CLIENT_ID,
                        "client_secret": settings.NAVER_CLIENT_SECRET,
                        "code": code,
                        "state": state,
                    },
                )
            else:  # google
                resp = await client.post(
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": settings.GOOGLE_CLIENT_ID,
                        "client_secret": settings.GOOGLE_CLIENT_SECRET,
                        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                        "code": code,
                    },
                )
    except httpx.RequestError as exc:
        raise InvalidRequestException(
            message=f"{provider} 인증 서버에 연결할 수 없습니다.",
            code="OAUTH_PROVIDER_UNAVAILABLE",
        ) from exc

    token_data = resp.json()
    access_token = token_data.get("access_token")
    if resp.status_code != 200 or not access_token:
        provider_error = str(token_data.get("error") or "unknown_error")
        provider_description = str(
            token_data.get("error_description") or "상세 사유 없음"
        )
        logger.warning(
            "%s OAuth 토큰 교환 실패: status=%s, error=%s, description=%s",
            provider,
            resp.status_code,
            provider_error,
            provider_description,
        )
        raise InvalidRequestException(
            message=(
                f"{provider} 인증 정보를 확인하지 못했습니다. "
                f"다시 로그인해 주세요. ({provider_error}: {provider_description})"
            ),
            code="OAUTH_TOKEN_EXCHANGE_FAILED",
        )

    return str(access_token)


async def fetch_user_info(provider: str, access_token: str) -> dict:
    """
    provider에서 사용자 정보 조회.
    반환 형태: {"provider_id": str, "email": str|None, "nickname": str, "profile_image_url": str|None}
    """
    _assert_provider(provider)

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
        # TODO(구현 필요): kakao email 미제공 이슈 해결 전까지 비활성화 (SUPPORTED_PROVIDERS에서도 제외됨)
        # if provider == "kakao":
        #     resp = await client.get(
        #         "https://kapi.kakao.com/v2/user/me",
        #         headers={"Authorization": f"Bearer {access_token}"},
        #     )
        #     resp.raise_for_status()
        #     data = resp.json()
        #     kakao_account = data.get("kakao_account", {})
        #     profile = kakao_account.get("profile", {})
        #     return {
        #         "provider_id": str(data["id"]),
        #         "email": kakao_account.get("email"),
        #         "nickname": profile.get("nickname", "카카오 사용자"),
        #         "profile_image_url": profile.get("profile_image_url"),
        #     }

            if provider == "naver":
                resp = await client.get(
                    "https://openapi.naver.com/v1/nid/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                resp.raise_for_status()
                data = resp.json().get("response", {})
                provider_id = data.get("id")
                if not provider_id:
                    raise InvalidRequestException(
                        message="네이버 사용자 식별 정보를 확인할 수 없습니다.",
                        code="OAUTH_PROFILE_INVALID",
                    )
                return {
                    "provider_id": str(provider_id),
                    "email": data.get("email"),
                    "nickname": data.get("nickname") or "네이버 사용자",
                    "profile_image_url": data.get("profile_image"),
                }

        # google
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
            data = resp.json()
            return {
                "provider_id": data["id"],
                "email": data.get("email"),
                "nickname": data.get("name") or "구글 사용자",
                "profile_image_url": data.get("picture"),
            }
    except httpx.HTTPError as exc:
        raise InvalidRequestException(
            message=f"{provider} 사용자 정보를 확인하지 못했습니다.",
            code="OAUTH_PROFILE_REQUEST_FAILED",
        ) from exc
