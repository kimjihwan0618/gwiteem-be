# Gwiteem Backend

날씨, 자동차 경로 안내, 관심 종목 시세를 제공하는 FastAPI 백엔드입니다.

## 빠른 시작

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m alembic upgrade head
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

- Swagger UI: http://localhost:8000/docs
- Health check: http://localhost:8000/health

## 주요 기능

- 현재 위치 기준 날씨와 24시간 예보
- 카카오모빌리티 자동차 길찾기, 지도 경로, 거리와 예상 비용
- 경로 즐겨찾기 등록·수정·삭제
- 국내·해외 주식 순위와 기간별 차트
- 로그인 사용자의 관심 종목 관리

카카오 공개 길찾기 API의 지원 범위에 맞춰 현재 서버가 계산하는 이동 수단은 자동차입니다.
대중교통·도보·자전거는 별도 제공사 계약 또는 API를 선택한 뒤 추가해야 합니다.

## 구조

```text
app/
├── main.py
├── core/
├── db/
├── models/
├── schemas/
├── routers/
├── services/
├── repositories/
└── external/
```

계층 의존 방향은 `routers → services → repositories → models`입니다.

## 테스트

```bash
python -m pytest
```

현재 자동화 테스트 파일은 아직 없습니다.
