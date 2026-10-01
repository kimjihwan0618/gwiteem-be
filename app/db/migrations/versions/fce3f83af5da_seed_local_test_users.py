"""로컬 로그인 테스트 사용자 20명을 추가한다.

Revision ID: fce3f83af5da
Revises: 4528840cd462
Create Date: 2026-10-01 15:10:16.752859

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "fce3f83af5da"
down_revision: Union[str, None] = "4528840cd462"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

SEED_TIMESTAMP = datetime(2026, 10, 1)
PASSWORD_HASH = "$2b$12$qGNyRg60/uBpPc3BkGrjCuWpCBhAbw9fGfU1sYARILs/Sx5raEJGq"
TEST_USERS = (
    ("minjun.kim842@gmail.com", "민준킴"),
    ("seoyeon.lee317@naver.com", "서연로그"),
    ("jihoon.park581@naver.com", "지훈이"),
    ("yujin.choi246@daum.net", "유진데이"),
    ("hyunwoo.jung934@gmail.com", "현우짱"),
    ("subin.kang725@naver.com", "수빈픽"),
    ("minjae.cho468@naver.com", "민재킴"),
    ("haneul.yoon153@gmail.com", "하늘빛"),
    ("doyoon.jang672@daum.net", "도윤쓰"),
    ("jia.lim389@naver.com", "지아몽"),
    ("seungwoo.han514@gmail.com", "승우맨"),
    ("chaewon.oh801@naver.com", "채원이"),
    ("junho.seo267@naver.com", "준호킴"),
    ("yerin.shin646@gmail.com", "예린별"),
    ("taeyoon.kwon928@daum.net", "태윤쓰"),
    ("daeun.song374@naver.com", "다은데이"),
    ("jaehyun.hwang719@gmail.com", "재현픽"),
    ("sohee.ahn482@naver.com", "소희몽"),
    ("jungwoo.bae836@naver.com", "정우킴"),
    ("yejin.moon195@gmail.com", "예진로그"),
)


def upgrade() -> None:
    """동일한 비밀번호를 사용하는 로컬 테스트 계정을 추가한다."""
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "INSERT INTO users "
            "(email, nickname, provider, provider_id, password_hash, "
            "profile_image_url, created_at, updated_at, last_login_at) "
            "VALUES (:email, :nickname, 'local', :email, :password_hash, "
            "NULL, :created_at, :updated_at, NULL)"
        ),
        [
            {
                "email": email,
                "nickname": nickname,
                "password_hash": PASSWORD_HASH,
                "created_at": SEED_TIMESTAMP,
                "updated_at": SEED_TIMESTAMP,
            }
            for email, nickname in TEST_USERS
        ],
    )


def downgrade() -> None:
    """이 마이그레이션에서 추가한 로컬 테스트 계정을 제거한다."""
    op.get_bind().execute(
        sa.text("DELETE FROM users WHERE email = ANY(:emails) AND provider = 'local'"),
        {"emails": [email for email, _ in TEST_USERS]},
    )
