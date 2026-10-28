"""빈 PostgreSQL을 현재 모델로 복구하고 재실행 가능한 더미데이터를 넣는다."""

import argparse
import asyncio
import importlib
from datetime import datetime, timedelta

from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, select, text
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.models  # noqa: F401
from app.core.config import settings
from app.db.base import Base
from app.models.choice import ChoiceQuestion, ChoiceReason
from app.models.user import User


def prepare_schema(connection: Connection, apply: bool) -> None:
    """빈 스키마만 생성하고 기존 스키마는 최신 모델과 일치하는지 확인한다."""
    scripts = ScriptDirectory.from_config(Config("alembic.ini"))
    head = scripts.get_current_head()
    tables = set(inspect(connection).get_table_names())
    context = MigrationContext.configure(connection)
    revisions = context.get_current_heads()
    if tables - {"alembic_version"}:
        if revisions != (head,):
            raise RuntimeError("기존 DB의 마이그레이션 상태를 확인한 뒤 alembic upgrade head를 실행하세요.")
        if compare_metadata(context, Base.metadata):
            raise RuntimeError("기존 DB와 모델이 다릅니다. 자동 변경하지 않습니다.")
        print("기존 스키마: 최신 모델 및 Alembic head와 일치")
        return
    if revisions:
        raise RuntimeError("테이블 없이 Alembic 이력만 남았습니다. 이력 상태를 먼저 확인하세요.")
    print(f"빈 스키마: 모델 테이블 {len(Base.metadata.tables)}개 생성 예정 / head={head}")
    if apply:
        # 초기 이력은 기존 레거시 테이블에 대한 ALTER이므로 빈 DB에 재생할 수 없다.
        Base.metadata.create_all(connection)
        if compare_metadata(context, Base.metadata):
            raise RuntimeError("생성된 스키마와 모델이 일치하지 않습니다.")
        context.stamp(scripts, "head")


async def seed_data(db: AsyncSession) -> None:
    """기존 카탈로그를 만들고 생성 계정의 참여 분포를 갱신한다."""
    from scripts.refresh_sample_data import EMAILS, NAMES, refresh_activity

    catalog = importlib.import_module(
        "app.db.migrations.versions.6108ff5d4fe3_seed_choice_question_catalog"
    )
    now = datetime.utcnow()
    users = []
    for email, name in zip(EMAILS, NAMES):
        user = await db.scalar(select(User).where(User.email == email))
        if user is None:
            user = User(email=email, nickname=name, provider="local", provider_id=email,
                        password_hash=None, created_at=now - timedelta(days=60))
            db.add(user)
            await db.flush()
        elif user.provider != "local" or user.provider_id != email:
            raise RuntimeError("생성 계정 식별자가 기존 계정과 충돌합니다.")
        users.append(user)
    for category, entries in catalog.QUESTION_CATALOG.items():
        for index, (title, option_a, option_b) in enumerate(entries):
            question = await db.scalar(select(ChoiceQuestion).where(
                ChoiceQuestion.title == title, ChoiceQuestion.category == category
            ))
            if question is None:
                question = ChoiceQuestion(
                    author_id=users[index % len(users)].id, category=category,
                    title=title, option_a=option_a, option_b=option_b,
                    is_daily=category == "daily" and index == 0,
                    is_active=True, published_at=now - timedelta(days=7),
                )
                db.add(question)
                await db.flush()
            if not await db.scalar(select(ChoiceReason.id).where(
                ChoiceReason.question_id == question.id
            ).limit(1)):
                db.add_all([ChoiceReason(question_id=question.id, label=label, sort_order=i)
                            for i, label in enumerate(catalog.REASON_LABELS, 1)])
    await db.flush()
    await refresh_activity(db)


async def main(apply: bool) -> None:
    """스키마와 더미데이터를 하나의 트랜잭션으로 적용한다."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False,
                                 connect_args={"timeout": 8}, pool_pre_ping=True)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL statement_timeout = '60s'"))
            await connection.execute(text("SELECT pg_advisory_xact_lock(20261028, 89)"))
            await connection.run_sync(prepare_schema, apply)
            if apply:
                async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                    from scripts.refresh_sample_data import backup_database

                    print(f"백업: {await backup_database(db)}")
                    await seed_data(db)
                    await db.commit()
        print("저장 완료" if apply else "미리보기 완료. --apply로 스키마 및 더미데이터를 저장하세요.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        asyncio.run(main(args.apply))
    except Exception as exc:
        # DB 드라이버의 예외에 접속정보나 SQL 파라미터가 포함될 수 있다.
        print(f"실행 실패: {type(exc).__name__}. DB 접속 상태와 스키마를 확인하세요.")
        raise SystemExit(1) from None
