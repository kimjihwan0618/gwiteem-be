"""카테고리별 선택 질문을 최소 10개로 확충한다.

Revision ID: 6108ff5d4fe3
Revises: 0bee734e8685
Create Date: 2026-10-01 14:53:20.540132
"""

from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6108ff5d4fe3"
down_revision: Union[str, None] = "0bee734e8685"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_TIMESTAMP = datetime(2026, 10, 1)
REASON_LABELS = (
    "현실적으로 더 유리해서",
    "내 성향에 더 잘 맞아서",
    "장기적으로 더 나은 선택이라서",
    "현재 내 상황에 더 적합해서",
)
QUESTION_CATALOG: dict[str, tuple[tuple[str, str, str], ...]] = {
    "work": (
        ("이직할 회사를 고를 때 더 중요한 것은?", "높은 연봉", "성장 기회"),
        ("일하기 좋은 조직을 하나 고른다면?", "자유로운 분위기", "체계적인 시스템"),
        ("출퇴근과 업무 만족도 중 하나를 고른다면?", "가까운 보통 회사", "먼 꿈의 회사"),
        ("업무 방식으로 더 잘 맞는 것은?", "혼자 깊게 집중", "팀과 자주 협업"),
        ("승진 기회가 왔을 때 선택한다면?", "빠른 승진과 책임", "안정적인 현재 역할"),
        ("근무 시간을 선택할 수 있다면?", "정해진 출퇴근", "유연하지만 변동적"),
        ("커리어 방향을 하나 고른다면?", "전문가로 성장", "관리자로 성장"),
        ("연차를 사용하는 방식으로 더 좋은 것은?", "길게 한 번에 사용", "짧게 자주 사용"),
    ),
    "spending": (
        ("여유 자금이 생기면 어디에 쓰고 싶은가요?", "여행 경험", "생활 가전"),
        ("콘텐츠를 이용하는 방식으로 더 좋은 것은?", "구독으로 편리하게", "구매해서 소유하기"),
        ("필요한 물건이 세일 예정이라면?", "세일까지 기다리기", "필요할 때 바로 사기"),
        ("같은 가격이라면 어떤 제품을 고를까요?", "중고 프리미엄 제품", "새 보급형 제품"),
        ("한 달 식비를 줄여야 한다면?", "외식 횟수 줄이기", "장보기 품목 줄이기"),
        ("결제 혜택으로 더 끌리는 것은?", "나중에 쓰는 포인트", "즉시 할인"),
        ("나를 위한 소비 방식으로 더 좋은 것은?", "큰 만족 한 번", "작은 만족 여러 번"),
        ("전자제품을 살 때 더 중요한 것은?", "공식 보증과 서비스", "낮은 구매 가격"),
    ),
    "relationship": (
        ("갈등이 생겼을 때 더 나은 방식은?", "바로 대화하기", "시간을 두고 대화하기"),
        ("친구가 약속을 취소했을 때 나는?", "사정을 이해한다", "서운함을 표현한다"),
        ("마음을 전하는 선물로 더 좋은 것은?", "실용적인 선물", "의미 있는 선물"),
        ("사람들과 보내는 시간으로 더 좋은 것은?", "여럿이 함께", "한 명과 깊게"),
        ("진심 어린 사과에서 더 중요한 것은?", "솔직한 말", "달라진 행동"),
        ("연인과 취미가 다를 때 어떻게 할까요?", "함께할 취미 찾기", "각자 취미 존중하기"),
        ("가족과 중요한 의견이 다를 때 나는?", "조언을 받아들인다", "내 선택을 따른다"),
        ("오랜만인 사람에게 마음을 표현한다면?", "SNS로 반응하기", "직접 연락하기"),
    ),
    "daily": (
        ("운동 시간을 하나 고른다면?", "아침 운동", "저녁 운동"),
        ("주말을 보내는 방식으로 더 좋은 것은?", "미리 계획하기", "그날 즉흥적으로"),
        ("휴대폰 알림을 관리한다면?", "필요할 때만 확인", "바로바로 확인"),
        ("이동 시간에 더 하고 싶은 것은?", "책이나 글 읽기", "음악 듣기"),
        ("집안일을 처리하는 방식은?", "매일 조금씩", "주말에 한꺼번에"),
        ("새로운 것을 배운다면?", "혼자 내 속도로", "수업에서 함께"),
        ("매일 먹는 식사를 고른다면?", "익숙하고 건강하게", "다양하고 새롭게"),
        ("하루의 여유가 생기면 어디로 갈까요?", "도시에서 즐기기", "자연에서 쉬기"),
        ("좋은 순간을 남기는 방식은?", "사진으로 기록", "눈으로 충분히 보기"),
    ),
}


def upgrade() -> None:
    """기존 활성 질문 수를 기준으로 카테고리별 부족분만 추가한다."""
    connection = op.get_bind()

    for category, candidates in QUESTION_CATALOG.items():
        active_count = int(
            connection.execute(
                sa.text(
                    "SELECT COUNT(*) FROM choice_questions "
                    "WHERE category = :category AND is_active IS TRUE"
                ),
                {"category": category},
            ).scalar_one()
        )
        remaining = max(0, 10 - active_count)
        if remaining == 0:
            continue

        active_titles = set(
            connection.execute(
                sa.text(
                    "SELECT title FROM choice_questions "
                    "WHERE category = :category AND is_active IS TRUE"
                ),
                {"category": category},
            ).scalars()
        )
        available = [item for item in candidates if item[0] not in active_titles]

        for title, option_a, option_b in available[:remaining]:
            question_id = connection.execute(
                sa.text(
                    "INSERT INTO choice_questions "
                    "(category, title, option_a, option_b, option_c, option_d, "
                    "is_daily, is_active, published_at, created_at, author_id) "
                    "VALUES (:category, :title, :option_a, :option_b, NULL, NULL, "
                    "FALSE, TRUE, :published_at, :created_at, NULL) RETURNING id"
                ),
                {
                    "category": category,
                    "title": title,
                    "option_a": option_a,
                    "option_b": option_b,
                    "published_at": SEED_TIMESTAMP,
                    "created_at": SEED_TIMESTAMP,
                },
            ).scalar_one()

            for sort_order, label in enumerate(REASON_LABELS, start=1):
                connection.execute(
                    sa.text(
                        "INSERT INTO choice_reasons "
                        "(question_id, label, sort_order) "
                        "VALUES (:question_id, :label, :sort_order)"
                    ),
                    {
                        "question_id": question_id,
                        "label": label,
                        "sort_order": sort_order,
                    },
                )


def downgrade() -> None:
    """이 마이그레이션에서 추가한 질문과 연결된 이유를 제거한다."""
    op.get_bind().execute(
        sa.text(
            "DELETE FROM choice_questions "
            "WHERE author_id IS NULL AND created_at = :created_at"
        ),
        {"created_at": SEED_TIMESTAMP},
    )
