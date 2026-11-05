"""
FastAPI 앱 진입점.
실행: uvicorn app.main:app --reload
"""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.access_log import ApiAccessLogMiddleware
from app.core.exceptions import AppException
from app.core.logging_config import configure_api_logging, load_logging_config
from app.routers import (
    auth,
    choice,
    user,
)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """로그 출력 자원을 시작하고 정상 종료 시 큐를 비운다."""
    with configure_api_logging(load_logging_config(settings.LOG_CONFIG_FILE)):
        yield


app = FastAPI(
    title=settings.APP_NAME,
    description="일상의 선택을 나누고 결과를 확인하는 서비스 API",
    version="0.1.0",
    lifespan=lifespan,
)

# TODO(구현 필요): 운영 단계에서는 allow_origins를 실제 프론트엔드 도메인으로 제한
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[settings.GUEST_SESSION_HEADER_NAME],
)
app.add_middleware(ApiAccessLogMiddleware)


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    """설계서 5.4/5.5 공통 에러 응답 포맷."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "error": {"code": exc.code, "message": exc.message},
        },
    )


# --- 라우터 등록 (모두 /api/v1 prefix) ---
API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(choice.router, prefix=API_PREFIX)
app.include_router(user.router, prefix=API_PREFIX)


@app.get("/health", tags=["health"])
async def health_check():
    """기동 확인용. 로드밸런서 헬스체크 등에 사용."""
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}
