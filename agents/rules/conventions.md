---
paths:
  - "app/**/*.py"
---

# 코드 컨벤션

- docstring/주석/예외 메시지: 한국어.
- 타입힌트 필수. `str | None` (PEP 604) 사용, `Optional[str]` 금지.
- 비동기 SQLAlchemy(`AsyncSession`) + `sqlalchemy.future.select` 패턴.
- 미구현 부분은 `# TODO(구현 필요): ...` 형식으로 표시. 구현 완료 시 주석 제거.
- 에러는 `app/core/exceptions.py`의 `AppException` 서브클래스(`NotFoundException`, `UnauthorizedException` 등)만 raise. FastAPI `HTTPException` 직접 사용 금지.
- 응답은 `ApiResponse[T]`(`app/schemas/common.py`)로 감싼다. 커서 페이지네이션 필요 시 `CursorPage[T]`.
- 인증 (`app/core/deps.py`): Public=Depends 없음 / Optional=`get_optional_user` / Required=`get_current_user`.
