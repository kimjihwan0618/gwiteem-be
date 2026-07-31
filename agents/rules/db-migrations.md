---
paths:
  - "app/models/**/*.py"
  - "app/db/**/*.py"
---

# DB / 마이그레이션 규칙

- Alembic 마이그레이션 직접 작성 금지 → `alembic revision --autogenerate`로 생성 후 검토.
- `app/models/news.py`의 임베딩 컬럼은 SQLite용 임시 타입. pgvector 전환 작업이 아니면 건드리지 않음.
