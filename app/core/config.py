"""
앱 전역 설정.
.env 파일을 읽어 Settings 객체로 노출한다.
다른 모듈에서는 `from app.core.config import settings` 로 사용.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- App ---
    APP_NAME: str = "gwiteem"
    APP_ENV: str = "development"
    DEBUG: bool = True

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://gwiteem_user:gwiteem_pass@localhost:5432/gwiteem"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- JWT ---
    JWT_SECRET_KEY: str = "CHANGE_ME_TO_RANDOM_SECRET"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_EXPIRE_DAYS: int = 14

    # --- OAuth ---
    KAKAO_CLIENT_ID: str = ""
    KAKAO_CLIENT_SECRET: str = ""
    KAKAO_REDIRECT_URI: str = ""

    NAVER_CLIENT_ID: str = ""
    NAVER_CLIENT_SECRET: str = ""
    NAVER_REDIRECT_URI: str = ""

    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # --- LLM / Embedding ---
    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str = "gpt-4o-mini"

    # --- 외부 데이터 API ---
    NAVER_NEWS_API_CLIENT_ID: str = ""
    NAVER_NEWS_API_CLIENT_SECRET: str = ""
    TOSS_SECURITIES_CLIENT_ID: str = ""
    TOSS_SECURITIES_CLIENT_SECRET: str = ""
    MAP_DIRECTIONS_API_KEY: str = ""
    WEATHER_API_KEY: str = ""

    # --- 게스트(비로그인) ---
    GUEST_SESSION_TTL_HOURS: int = 24
    GUEST_SESSION_HEADER_NAME: str = "X-Guest-Session-Id"

    # --- 게스트 기본값 (지역/경로 미지정 시 사용) ---
    DEFAULT_WEATHER_LAT: float = 37.5665
    DEFAULT_WEATHER_LNG: float = 126.9780

    DEFAULT_COMMUTE_ORIGIN_LABEL: str = "강남역"
    DEFAULT_COMMUTE_ORIGIN_LAT: float = 37.4979
    DEFAULT_COMMUTE_ORIGIN_LNG: float = 127.0276
    DEFAULT_COMMUTE_DESTINATION_LABEL: str = "서울역"
    DEFAULT_COMMUTE_DESTINATION_LAT: float = 37.5547
    DEFAULT_COMMUTE_DESTINATION_LNG: float = 126.9707

    # --- RAG ---
    NEWS_CLUSTER_SIMILARITY_THRESHOLD: float = 0.85

    # --- AWS SES (이메일 인증) ---
    AWS_REGION: str = "ap-northeast-2"
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    SES_SENDER_EMAIL: str = "noreply@gwiteem.com"
    EMAIL_VERIFICATION_CODE_TTL_MINUTES: int = 5
    EMAIL_VERIFIED_TTL_MINUTES: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
