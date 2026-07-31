---
paths:
  - "app/**/*.py"
---

# 계층 의존 규칙

`routers → services → repositories → models`

- routers: 요청/응답 검증 + 인증(Depends)만 담당. DB 쿼리 직접 작성 금지.
- services: 비즈니스 로직. DB 접근은 반드시 repositories 경유.
- repositories: 순수 DB 쿼리 캡슐화만. 권한 체크/조합 로직 넣지 않음.
- external/*_client.py: 외부 API 호출 캡슐화. services에 직접 넣지 않음.
