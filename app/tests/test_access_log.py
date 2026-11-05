"""인증 상태와 HTTP 결과에 따른 요청 로그를 검증한다."""
import re
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from app.core.access_log import ApiAccessLogMiddleware
from app.core.deps import get_current_user, get_db, get_optional_user
from app.core.exceptions import AppException
from app.models.user import User


@pytest.mark.asyncio
@pytest.mark.parametrize("method", ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"])
@pytest.mark.parametrize(
    "path,user_id,status,actor,outcome",
    [
        ("/api/public?token=secret", None, 200, "public", "success"),
        ("/api/optional", None, 200, "public", "success"),
        ("/api/optional", 42, 200, "42", "success"),
        ("/api/required", 42, 200, "42", "success"),
        ("/api/required", None, 401, "public", "failed"),
        ("/api/validation?number=bad", None, 422, "public", "failed"),
        ("/api/missing", None, 404, "public", "failed"),
        ("/api/error", 42, 500, "42", "failed"),
    ],
)
async def test_api_access_log(method: str, path: str, user_id: int | None, status: int, actor: str, outcome: str) -> None:
    app = FastAPI()
    app.add_middleware(ApiAccessLogMiddleware)

    async def unused_db() -> AsyncGenerator[None, None]:
        yield None

    app.dependency_overrides[get_db] = unused_db

    @app.exception_handler(AppException)
    async def handle_error(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse({"success": False}, status_code=exc.status_code)

    @app.api_route("/api/public", methods=[method])
    async def public() -> dict[str, bool]:
        return {"success": True}

    @app.api_route("/api/optional", methods=[method])
    async def optional(user: User | None = Depends(get_optional_user)) -> dict[str, bool]:
        return {"success": True}

    @app.api_route("/api/required", methods=[method])
    async def required(user: User = Depends(get_current_user)) -> dict[str, bool]:
        return {"success": True}

    @app.api_route("/api/validation", methods=[method])
    async def validation(number: int) -> dict[str, int]:
        return {"number": number}

    @app.api_route("/api/error", methods=[method])
    async def error(user: User = Depends(get_current_user)) -> None:
        raise RuntimeError("테스트용 예외")

    user = User(id=user_id) if user_id is not None else None
    with patch("app.core.deps._resolve_user_from_token", new=AsyncMock(return_value=user)), patch("app.core.access_log.logger.log") as log:
        async with AsyncClient(transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test") as client:
            response = await client.request(method, path)
        assert response.status_code == status
        log.assert_called_once()
        level, template, timestamp, actual_actor, actual_method, actual_path, actual_outcome = log.call_args.args
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", timestamp)
        assert (actual_actor, actual_path, actual_outcome) == (actor, path.split("?")[0], outcome)
        assert actual_method == method
        assert template == "%s, [%s], %s, %s, %s"


@pytest.mark.asyncio
async def test_health_is_not_logged() -> None:
    app = FastAPI()
    app.add_middleware(ApiAccessLogMiddleware)
    with patch("app.core.access_log.logger.log") as log:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.get("/health")
        log.assert_not_called()
