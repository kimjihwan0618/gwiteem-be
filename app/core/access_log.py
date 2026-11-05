"""API 요청 결과를 한국 시간, 인증 사용자, HTTP 메서드, 경로, 성공 여부 순서로 기록한다."""
import logging
from datetime import datetime, timedelta, timezone

from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("gwiteem.api_access")

KST = timezone(timedelta(hours=9))


class ApiAccessLogMiddleware:
    """응답 본문을 버퍼링하지 않고 API 요청마다 한 줄을 출력한다."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        timestamp = datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S")
        state = scope.setdefault("state", {})
        state["access_log_user_id"] = None
        status_code = 500
        completed = False

        async def capture_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, capture_status)
            completed = True
        finally:
            identity = state.get("access_log_user_id")
            actor = str(identity) if identity is not None else "public"
            # 개행·제어문자로 로그 행이 분리되지 않도록 하고 query는 기록하지 않는다.
            safe_path = "".join(char if char.isprintable() else "?" for char in path)
            outcome = "success" if completed and 200 <= status_code < 400 else "failed"
            level = logging.ERROR if not completed or status_code >= 500 else (
                logging.WARNING if status_code >= 400 else logging.INFO
            )
            logger.log(level, "%s, [%s], %s, %s, %s", timestamp, actor, scope["method"], safe_path, outcome)
