# 질문 목록, 검색, 대댓글 API

질문 목록은 서버에서 검색·카테고리·정렬 조건을 적용한 뒤 최대 15개를 반환한다.
프론트엔드는 lodash.debounce로 입력이 멈춘 뒤 0.3초 후 조회하고, 목록 하단에
도달하면 `next_cursor`로 다음 페이지를 불러온다. 한글 조합 중에는 검색을 보류한다.

다음 세 조회 API가 동일한 query parameter를 받는다.

- `GET /api/v1/choices/questions`: 공개 질문 목록
- `GET /api/v1/choices/me`: 로그인 사용자의 참여 기록
- `GET /api/v1/choices/me/likes`: 로그인 사용자의 좋아요 기록

| 파라미터 | 설명 |
| --- | --- |
| `limit` | 기본 15, 최대 15 |
| `cursor` | 직전 응답의 `next_cursor`, 첫 요청은 생략 |
| `q` | 질문 제목 부분 검색, 최대 200자. `%`, `_`도 문자 그대로 검색 |
| `category` | `work`, `spending`, `relationship`, `daily`. 여러 개는 반복 전달 |
| `sort` | `popular`(참여순, 기본), `liked`(좋아요순), `latest`(질문 게시 최신순) |

```text
GET /api/v1/choices/questions?limit=15&q=출근&category=work&category=daily&sort=latest
```

응답 `data`는 `{ "items": [...], "next_cursor": "..." }`이며 마지막 페이지는
`next_cursor`가 `null`이다. 내 기록 API도 종전 배열 대신 이 페이지 객체를 반환한다.
BE와 FE를 함께 배포해야 한다.

커서는 정렬 지표, 게시 시각, 질문 ID를 사용한다. 같은 지표·게시 시각에서도 ID로
순서를 결정한다. 필터나 사용자, 목록 종류가 바뀌면 커서를 버리고 처음부터 조회한다.
참여·좋아요 수는 실시간으로 변하므로 고정 스냅샷은 아니며 FE에서도 ID를 기준으로
중복 표시를 방지한다. 다음 페이지 실패 시 기존 목록과 재시도 버튼을 유지한다.

대댓글은 기존 `choice_replies` 모델과 API를 사용한다. 댓글에서 답글 쓰기 및 펼치기를
제공하며, 작성은 로그인 필수이고 수정·삭제는 작성자만 가능하다. 한 단계 답글이며
상위 댓글 삭제 시 답글도 삭제된다. 별도 스키마 변경은 없다.

```text
POST   /api/v1/choices/questions/{question_id}/comments/{comment_id}/replies
PATCH  /api/v1/choices/questions/{question_id}/comments/{comment_id}/replies/{reply_id}
DELETE /api/v1/choices/questions/{question_id}/comments/{comment_id}/replies/{reply_id}
```

검증: `python -m pytest app/tests -q`로 페이지 경계, 모든 정렬, 서버 검색,
다중 카테고리, 잘못된 커서, 사용자별 기록, 대댓글 권한과 연쇄 삭제를 확인한다.
