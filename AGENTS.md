@CLAUDE.md

# BE 바이브 코딩 규칙

`BE` 프로젝트의 코드를 작성·수정·리뷰할 때는 작업을 시작하기 전에
`agents/rules/` 디렉터리의 규칙을 확인하고 반드시 준수한다.

- `agents/rules/architecture.md`
- `agents/rules/conventions.md`
- `agents/rules/db-migrations.md`
- `agents/rules/scope-guardrails.md`

각 규칙 파일의 `paths` 조건이 현재 작업 파일과 일치하면 해당 규칙을 적용한다.
`paths` 조건이 없는 규칙은 `BE` 프로젝트 전체에 적용한다.
