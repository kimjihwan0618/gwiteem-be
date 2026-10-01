"""기본 질문을 테스트 사용자에게 균등 배정한다.

Revision ID: 947cff0bfa96
Revises: dae844e0f9d2
Create Date: 2026-10-01 16:11:49.665182

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "947cff0bfa96"
down_revision: Union[str, None] = "dae844e0f9d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ASSIGNMENT_CUTOFF = datetime(2026, 10, 1, 23, 59, 59)
TEST_USER_EMAILS = (
    "minjun.kim842@gmail.com",
    "seoyeon.lee317@naver.com",
    "jihoon.park581@naver.com",
    "yujin.choi246@daum.net",
    "hyunwoo.jung934@gmail.com",
    "subin.kang725@naver.com",
    "minjae.cho468@naver.com",
    "haneul.yoon153@gmail.com",
    "doyoon.jang672@daum.net",
    "jia.lim389@naver.com",
    "seungwoo.han514@gmail.com",
    "chaewon.oh801@naver.com",
    "junho.seo267@naver.com",
    "yerin.shin646@gmail.com",
    "taeyoon.kwon928@daum.net",
    "daeun.song374@naver.com",
    "jaehyun.hwang719@gmail.com",
    "sohee.ahn482@naver.com",
    "jungwoo.bae836@naver.com",
    "yejin.moon195@gmail.com",
)


def upgrade() -> None:
    """작성자가 없는 기존 질문을 테스트 사용자에게 순환 배정한다."""
    connection = op.get_bind()
    user_ids = list(
        connection.execute(
            sa.text(
                "SELECT id FROM users "
                "WHERE provider = 'local' AND email = ANY(:emails) "
                "ORDER BY email"
            ),
            {"emails": list(TEST_USER_EMAILS)},
        ).scalars()
    )
    if not user_ids:
        raise RuntimeError("질문 작성자로 배정할 테스트 사용자가 없습니다.")

    question_ids = list(
        connection.execute(
            sa.text(
                "SELECT id FROM choice_questions "
                "WHERE author_id IS NULL AND created_at <= :cutoff "
                "ORDER BY category, id"
            ),
            {"cutoff": ASSIGNMENT_CUTOFF},
        ).scalars()
    )
    for index, question_id in enumerate(question_ids):
        connection.execute(
            sa.text(
                "UPDATE choice_questions SET author_id = :author_id "
                "WHERE id = :question_id AND author_id IS NULL"
            ),
            {
                "author_id": user_ids[index % len(user_ids)],
                "question_id": question_id,
            },
        )


def downgrade() -> None:
    """이 마이그레이션에서 배정한 기본 질문 작성자를 비운다."""
    op.get_bind().execute(
        sa.text(
            "UPDATE choice_questions SET author_id = NULL "
            "WHERE created_at <= :cutoff AND author_id IN ("
            "SELECT id FROM users WHERE provider = 'local' AND email = ANY(:emails)"
            ")"
        ),
        {"cutoff": ASSIGNMENT_CUTOFF, "emails": list(TEST_USER_EMAILS)},
    )
