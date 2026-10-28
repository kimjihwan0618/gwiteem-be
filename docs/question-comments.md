# 질문별 댓글

## 대댓글

`87af8eca06fd` 마이그레이션은 `choice_replies` 테이블을 추가한다.
대댓글은 한 단계만 지원하며 좋아요 필드와 API가 없다.
댓글 목록의 각 `items[].replies`에 작성 시간순으로 포함되고,
카드와 탭의 `comment_count`는 원댓글 수를 유지한다.

- `POST /api/v1/choices/questions/{question_id}/comments/{comment_id}/replies`: 답글 등록
- `PATCH .../replies/{reply_id}`: 본인 답글 수정
- `DELETE .../replies/{reply_id}`: 본인 답글 삭제

댓글과 동일하게 로그인 및 공백 제거 후 1~1,000자 검증을 적용한다.
다른 질문이나 댓글의 답글에 접근할 수 없으며 원댓글 삭제 시 답글도 함께 삭제된다.

### 더미 대화 데이터

기존 테스트 계정 마이그레이션에 명시된 로컬 계정만 사용한다. 새 사용자는 만들지 않는다.
기존 댓글과 답글을 유지하고 질문마다 댓글 8~12개, 모든 댓글에 답글 1~3개를 목표로 보충한다.
다시 실행해도 목표 개수에 도달한 글은 더 생성하지 않는다.

```bash
python -m scripts.seed_choice_discussions          # 미리보기 후 롤백
python -m scripts.seed_choice_discussions --apply  # 저장
```

이 스크립트는 서비스 운영용 데이터가 아닌 개발·데모용 합성 데이터를 생성한다.

### 더미 선택 데이터

`python -m scripts.seed_choice_votes --apply`는 기존 더미 계정 중 질문별 70~100%가
참여하도록 투표를 보충한다. 기본 난수 시드는 고정되어 같은 명령을 다시 실행해도
목표 인원이 바뀌지 않는다. `--apply`를 생략하면 검증 후 롤백한다.
질문에 등록된 선택지·필수 이유만 사용하며 기존 투표는 변경하지 않는다.
더미 계정 외 사용자·게스트의 기존 투표는 별도로 유지되므로 화면의 총 참여 수는
더미 계정의 목표 인원보다 클 수 있다.

질문 목록·상세·내 선택·좋아요 목록에 `comment_count`를 포함한다.
댓글은 투표 여부와 관계없이 읽을 수 있고, 작성과 좋아요에는 로그인이 필요하다.
수정·삭제는 작성자만 가능하며 비활성 질문은 조회·변경할 수 없다.

## API

기본 경로: `/api/v1/choices/questions/{question_id}/comments`

| 메서드 | 경로 | 동작 |
| --- | --- | --- |
| GET | 기본 경로 | 최신 ID 순 20개, `cursor`로 다음 페이지 조회 |
| POST | 기본 경로 | 댓글 등록 |
| PATCH | `/{comment_id}` | 본인 댓글 수정 |
| DELETE | `/{comment_id}` | 본인 댓글 삭제 |
| PUT | `/{comment_id}/like` | 좋아요 설정, 반복 요청에 멱등 |
| DELETE | `/{comment_id}/like` | 좋아요 해제, 반복 요청에 멱등 |

등록·수정 요청은 `{ "content": "댓글 내용" }`이며 앞뒤 공백을 제거한 1~1,000자다.
조회 응답은 `ApiResponse`의 `data`에 `items`, `next_cursor`, `total_count`를 담는다.
변경 응답은 `data.id`와 사용자에게 표시할 `message`를 담는다.
댓글 좋아요 변경은 댓글 행 잠금으로 직렬화하고 `(comment_id, user_id)` 유일 제약을 둔다.
질문·사용자 삭제 시 댓글을, 댓글 삭제 시 좋아요를 DB 외래키 CASCADE로 정리한다.

## 마이그레이션과 검증

`1c159ec384dd_add_question_comments.py`는 `alembic revision --autogenerate`로 생성했다.
직전 버전은 `947cff0bfa96`이며 댓글·댓글 좋아요 테이블과 인덱스만 추가한다.

```bash
alembic upgrade head
alembic check
python -m pytest app/tests/test_comments.py -q
```

API 테스트는 격리된 메모리 SQLite DB를 사용한다. 실행 환경에 `aiosqlite`가 필요하다.
권한, 내용 검증, 커서 안정성, 집계, 멱등 좋아요, 연쇄 삭제와 마이그레이션 적용·롤백을 검증한다.
롤백은 `alembic downgrade 947cff0bfa96`이며 댓글 데이터가 삭제되므로 운영 데이터가 있으면 먼저 백업한다.
