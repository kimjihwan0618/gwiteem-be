# Gwiteem Backend

**오늘, 당신의 선택은?** Gwiteem은 일상의 고민을 질문으로 만나고, 자신의 선택과 이유를 남긴 뒤 다른 사람들의 생각을 확인하는 서비스입니다.

직장·소비·관계·일상 네 가지 주제에서 가볍게 참여하고, 투표 결과와 댓글로 서로의 관점을 나눕니다. 이 저장소는 질문 탐색, 투표와 결과 집계, 좋아요, 댓글·답글, 사용자 인증과 내 기록을 제공하는 FastAPI 백엔드입니다.

## 주요 기능

- **질문 탐색**: 오늘의 질문 표시, 카테고리 필터, 제목 검색, 참여순·최신순·좋아요순 정렬, 커서 페이지네이션
- **투표와 결과**: 선택지와 이유를 함께 제출하고, 참여 후 선택지별 비율과 이유별 집계 확인. 기존 선택 변경 지원
- **게스트 참여**: 비로그인 투표와 브라우저별 선택 기록, 로그인 시 게스트 기록 병합
- **질문 좋아요와 내 기록**: 질문 좋아요 설정·해제, 참여한 질문과 좋아요한 질문 조회
- **댓글과 답글**: 공개 조회, 로그인 후 작성·댓글 좋아요, 작성자 본인의 수정·삭제, 한 단계 답글
- **인증**: 이메일 가입·인증·로그인, 비밀번호 재설정, 카카오·네이버·Google OAuth, 토큰 갱신·로그아웃·회원 탈퇴

질문 작성·발행을 위한 일반 사용자용 화면/API는 현재 제공하지 않습니다. 등록된 질문을 탐색하고 참여하는 흐름이 현재 서비스의 중심입니다.

## 이용 권한

| 기능                     | 비로그인             | 로그인            |
| ------------------------ | -------------------- | ----------------- |
| 질문·댓글 조회           | 가능                 | 가능              |
| 투표·선택 변경           | 게스트 식별자로 가능 | 계정으로 가능     |
| 결과 조회                | 해당 질문 참여 후    | 해당 질문 참여 후 |
| 질문·댓글 좋아요         | 불가                 | 가능              |
| 댓글·답글 작성           | 불가                 | 가능              |
| 댓글·답글 수정·삭제      | 불가                 | 작성자만 가능     |
| 내 선택·좋아요 기록 조회 | 불가                 | 가능              |

게스트 식별자는 `X-Guest-Session-Id` 헤더로 전달합니다. 로그인 사용자는 Bearer 토큰으로 인증합니다. 프론트엔드에서는 Next.js Route Handler가 HTTP-only 쿠키의 토큰을 읽어 백엔드로 전달합니다.

## 기술 스택

- FastAPI, Pydantic, Uvicorn
- PostgreSQL, 비동기 SQLAlchemy, asyncpg
- Alembic: 스키마 마이그레이션
- JWT, bcrypt, OAuth: 사용자 인증
- Redis, AWS SES: 이메일 인증 등 인증 관련 저장소·발송 연동
- pytest, pytest-asyncio, aiosqlite: 자동화 테스트

## 로컬 실행

### 환경 준비

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS/Linux에서는 `source .venv/bin/activate`로 가상환경을 활성화합니다.

저장소 루트의 `.env`에 실행 환경을 설정합니다. 아래 값은 예시이며 실제 PostgreSQL·Redis 연결 정보와 별도 생성한 JWT 비밀키로 바꿉니다.

```env
APP_ENV=development
DATABASE_URL=postgresql+asyncpg://USER:PASSWORD@localhost:5432/gwiteem
REDIS_URL=redis://localhost:6379/0
JWT_SECRET_KEY=replace-with-a-random-secret
```

추가 설정은 [설정 정의](app/core/config.py)를 참고하세요. 이메일 인증·비밀번호 재설정에는 AWS SES 설정이, 소셜 로그인에는 해당 제공사의 client 정보와 redirect URI 설정이 필요합니다.

### DB 준비

기존 마이그레이션 이력이 있는 DB는 다음 명령으로 최신 스키마를 적용합니다.

```bash
python -m alembic upgrade head
```

완전히 빈 DB는 최초 마이그레이션이 레거시 테이블의 변경부터 시작하므로 위 명령만으로 초기화할 수 없습니다. 이 경우 [DB 초기화·샘플 데이터 안내](docs/database-bootstrap.md)에 따라 상태를 확인하고 초기화합니다.

```bash
python -m scripts.bootstrap_database
python -m scripts.bootstrap_database --apply
```

`--apply`는 빈 스키마에 현재 모델의 테이블을 만들고 Alembic head를 기록하며 샘플 데이터를 생성합니다. 샘플 사용자는 비밀번호가 없는 합성 데이터이므로 로그인용 계정으로 사용할 수 없습니다.

### 서버 실행

```bash
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- [Swagger UI](http://localhost:8000/docs)
- [Health check](http://localhost:8000/health)

프론트엔드의 `API_BASE_URL`에는 `http://localhost:8000`을 설정합니다.

## 주요 API

기본 prefix는 `/api/v1`입니다. 아래 표는 상대 경로이며, 상세 요청·응답 스키마는 Swagger UI에서 확인할 수 있습니다.

| 메서드         | 경로                                                               | 용도                             |
| -------------- | ------------------------------------------------------------------ | -------------------------------- |
| GET            | `/choices/questions`                                               | 질문 목록·검색·필터·정렬         |
| GET            | `/choices/questions/{id}`                                          | 질문 상세와 참여 후 결과         |
| POST           | `/choices/questions/{id}/votes`                                    | 투표 또는 선택 변경              |
| PUT / DELETE   | `/choices/questions/{id}/like`                                     | 질문 좋아요 설정·해제            |
| POST           | `/choices/votes/migrate`                                           | 게스트 투표를 로그인 계정에 병합 |
| GET            | `/choices/me`                                                      | 내 참여 기록                     |
| GET            | `/choices/me/likes`                                                | 내가 좋아요한 질문               |
| GET / POST     | `/choices/questions/{id}/comments`                                 | 댓글 목록·등록                   |
| PATCH / DELETE | `/choices/questions/{id}/comments/{comment_id}`                    | 본인 댓글 수정·삭제              |
| PUT / DELETE   | `/choices/questions/{id}/comments/{comment_id}/like`               | 댓글 좋아요 설정·해제            |
| POST           | `/choices/questions/{id}/comments/{comment_id}/replies`            | 답글 등록                        |
| PATCH / DELETE | `/choices/questions/{id}/comments/{comment_id}/replies/{reply_id}` | 본인 답글 수정·삭제              |

목록 조회는 `q`, `category`, `sort`, `limit`, `cursor`를 받으며 질문·내 기록은 최대 15개씩 반환합니다. 프론트에서는 검색 아이콘 또는 Enter로 검색을 실행하고, X 버튼으로 검색어를 초기화합니다. API는 전달받은 검색 조건으로 조회합니다.

댓글은 최신순 20개씩 조회하고 내용은 공백 제거 후 1~1,000자입니다. 답글은 한 단계만 지원하고 좋아요는 없습니다. 질문의 `comment_count`는 답글을 제외한 원댓글 수이며, 원댓글 삭제 시 답글도 함께 삭제됩니다.

- [질문 목록·검색·페이지네이션](docs/question-feed.md)
- [댓글·답글 API와 검증](docs/question-comments.md)

공통 응답은 `ApiResponse[T]`를 사용합니다.

```json
{
  "success": true,
  "data": {},
  "error": null
}
```

오류 응답은 `success: false`, `data: null`, `error: { "code": "...", "message": "..." }` 형태입니다.

## 구조

```text
app/
  main.py          # FastAPI 앱, 라우터 등록, 공통 예외 처리
  core/            # 설정, 인증 의존성, 예외
  db/              # DB 세션과 Alembic 마이그레이션
  models/          # 사용자·질문·투표·좋아요·댓글·답글 모델
  schemas/         # 요청·응답 검증
  routers/         # 인증·질문·댓글·사용자 API
  services/        # 권한과 서비스 로직
  repositories/    # DB 조회·저장
  external/        # 외부 서비스 연동
  tests/           # API·페이지네이션·샘플 데이터 테스트
scripts/           # DB 초기화와 개발용 데이터 관리
```

계층 의존 방향은 `routers → services → repositories → models`입니다. 요청과 인증 처리는 router, 서비스 규칙은 service, DB 접근은 repository에서 담당합니다.

## API 요청 로그

`/api/` 아래 요청은 콘솔과 롤링 파일에 다음 형식으로 한 줄씩 기록됩니다.

```text
2026-11-05 14:30:00, [public], POST, /api/v1/auth/login, success
2026-11-05 14:30:01, [42], POST, /api/v1/choices/questions/1/like, success
2026-11-05 14:30:02, [public], POST, /api/v1/auth/password/reset-code, failed
```

- 시간: 요청 시작 시각, 한국 시간(KST), 24시간 표기.
- 사용자: Required/Optional 인증 의존성이 검증한 사용자 ID. 미인증·인증 실패·인증을 수행하지 않는 공개 API는 `public`입니다. 로그인 API 자체는 공개 요청이므로 성공해도 `public`입니다.
- HTTP 메서드: GET, POST, PUT, PATCH, DELETE 등 실제 요청 메서드를 경로 앞에 기록합니다.
- 경로: query string 없이 실제 요청 path만 기록합니다. 토큰·비밀번호·요청/응답 본문은 기록하지 않습니다.
- 결과: HTTP 200~399는 `success`, 400 이상 또는 처리 중 예외는 `failed`입니다.
- `/health`, 문서 및 WebSocket은 대상에서 제외합니다. Uvicorn 기본 접근 로그와는 별도이며, 컨테이너에서는 기존 로그 수집 방식으로 조회할 수 있습니다.

## 테스트

```bash
python -m pytest app/tests -q
```

댓글·답글 권한과 좋아요, 페이지네이션·검색·정렬, 샘플 데이터의 일관성과 보존을 검증합니다. 테스트는 격리된 SQLite DB 등을 사용하며 필요한 패키지는 `requirements.txt`에 포함돼 있습니다.

### 로그 라이브러리와 설정

현재 단일 Uvicorn 프로세스 구조에 맞춰 Python 표준 `logging`을 사용합니다. Loguru의 별도 로거 연동이나 structlog의 구조화 이벤트 처리가 필요하지 않아 추가 의존성 없이 표준 롤링 핸들러를 채택했습니다. `QueueHandler` / `QueueListener`로 파일 I/O를 별도 스레드에서 처리하며 정상 종료 시 큐를 비우고 파일을 닫습니다.

설정 파일은 `app/logging.toml`입니다. 다른 파일을 사용하려면 `.env` 또는 실행 환경에 `LOG_CONFIG_FILE=/app/config/logging.toml`을 설정합니다. 변경 후 서버를 재시작해야 합니다. 잘못된 설정이나 쓰기 불가능한 경로는 시작 시 오류로 표시됩니다.

| 설정 | 기본값 | 의미 |
|---|---|---|
| `level` | `INFO` | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `console_enabled` | `true` | stderr 출력 |
| `file_enabled` | `true` | 파일 출력 |
| `file_path` | `logs/api-access.log` | 절대 경로 또는 BE 루트 기준 상대 경로, 디렉터리 자동 생성 |
| `rotation` | `size` | `size` 또는 `time` |
| `max_bytes` | `10485760` | size 모드에서 약 10MiB마다 분리 |
| `backup_count` | `14` | 활성 파일 외 백업 최대 14개, 롤링 시 오래된 파일 삭제 |
| `when` | `midnight` | time 모드에서 S/M/H/D/midnight/W0~W6 |
| `interval` | `1` | 시간 롤링 주기 |
| `utc` | `true` | 시간 롤링 UTC 기준; false이면 서버 로컬 시간 |

성공 요청은 INFO, HTTP 4xx는 WARNING, 5xx·예외는 ERROR 레벨입니다. `level = "WARNING"`이면 실패 요청만 남습니다. 출력 순서는 시간, 사용자, HTTP 메서드, 경로, 성공 여부입니다. 이 설정은 API 접근 로그 전용이며 Uvicorn 및 다른 애플리케이션 로그 정책은 바꾸지 않습니다.

용량 모드는 `api-access.log.1`~`.14`, 시간 모드는 `api-access.log.날짜` 형식으로 보관합니다. 예를 들어 `rotation = "time"`, `when = "midnight"`, `interval = 1`이면 매일 경계 이후 첫 로그에서 롤링합니다. `backup_count`는 보관 일수가 아니라 파일 개수입니다. 로그에 찍히는 요청 시간은 계속 KST이며 UTC 자정 롤링은 KST 오전 9시에 해당합니다. 시간 모드에서는 `max_bytes`가 적용되지 않습니다.

기본 로그 경로는 로컬에서 `<BE>/logs/api-access.log`, NAS의 `/app` 마운트 배포에서는 `/app/logs/api-access.log`입니다. 로그를 배포 파일과 분리하려면 영속 디렉터리를 `/var/log/gwiteem`에 마운트하고 `file_path = "/var/log/gwiteem/api-access.log"`로 설정하세요. 실제 NAS 마운트 변경은 별도로 적용해야 합니다. 기본 TOML은 `app` 디렉터리와 함께 배포 패키지에 포함됩니다.

표준 롤링 파일은 단일 프로세스용입니다. 여러 worker/컨테이너가 동일 파일에 기록하도록 구성하지 마세요. 다중 프로세스로 확장할 때는 `file_enabled = false`와 콘솔 로그 수집기의 롤링을 사용하거나 프로세스별 독립 파일 경로로 분리해야 합니다. 기존 Uvicorn 접근 로그는 별도 출력되며 필요하면 실행 옵션 `--no-access-log`로 중복 접근 로그를 끌 수 있습니다.