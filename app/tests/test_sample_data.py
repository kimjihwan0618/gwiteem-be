"""생성 데이터 갱신 시 이름, 분포, 사용자 작성 데이터 보존을 검증한다."""

import pytest
from sqlalchemy import event, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.db.base import Base
from app.models.choice import ChoiceLike, ChoiceQuestion
from app.models.comment import ChoiceComment, ChoiceReply
from app.models.user import User
from scripts.bootstrap_database import seed_data
from scripts.refresh_sample_data import NAMES, refresh_activity


@pytest.mark.asyncio
async def test_sample_refresh_preserves_written_activity() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enable_foreign_keys(connection: object, record: object) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                await seed_data(db)
                names = set((await db.scalars(select(User.nickname))).all())
                assert names == set(NAMES) and all(len(name) == 3 for name in names)
                comment = await db.scalar(select(ChoiceComment).order_by(ChoiceComment.id))
                assert comment is not None
                user = User(nickname="보존회원", provider="local", provider_id="preserve")
                db.add(user)
                await db.flush()
                # 생성 계정으로 직접 입력한 답글과 다른 사용자의 댓글·좋아요를 함께 보존한다.
                reply = ChoiceReply(comment_id=comment.id, user_id=comment.user_id,
                                    content="직접 입력한 답글입니다.")
                own_comment = ChoiceComment(question_id=comment.question_id, user_id=user.id,
                                             content="직접 작성한 댓글입니다.")
                own_like = ChoiceLike(question_id=comment.question_id, user_id=user.id)
                db.add_all([reply, own_comment, own_like])
                await db.flush()
                protected = {
                    table.name: [dict(row) for row in (await db.execute(select(table).where(table.c.id == row_id))).mappings()]
                    for table, row_id in ((User.__table__, user.id), (ChoiceReply.__table__, reply.id),
                                          (ChoiceComment.__table__, own_comment.id), (ChoiceLike.__table__, own_like.id))
                }
                counts = await refresh_activity(db)
                assert counts["choice_questions"] == 33
                assert len({counts[key] for key in ("choice_comments", "choice_replies", "choice_likes", "choice_comment_likes")}) == 4
                for table, row_id in ((User.__table__, user.id), (ChoiceReply.__table__, reply.id),
                                      (ChoiceComment.__table__, own_comment.id), (ChoiceLike.__table__, own_like.id)):
                    rows = [dict(row) for row in (await db.execute(select(table).where(table.c.id == row_id))).mappings()]
                    assert rows == protected[table.name]
                assert await db.get(ChoiceComment, comment.id) is not None
                assert await refresh_activity(db) == counts
                assert not (await connection.exec_driver_sql("PRAGMA foreign_key_check")).all()
                assert await db.scalar(text(
                    "SELECT count(*) FROM choice_votes v JOIN choice_reasons r ON r.id=v.reason_id "
                    "WHERE v.question_id != r.question_id"
                )) == 0
                question_counts = list((await db.execute(select(
                    ChoiceQuestion.id, func.count(ChoiceComment.id)
                ).outerjoin(ChoiceComment).group_by(ChoiceQuestion.id)) ).all())
                assert len({count for _, count in question_counts}) > 5
    finally:
        await engine.dispose()
