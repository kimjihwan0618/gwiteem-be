"""일상 선택 질문과 투표 DB 접근."""

from sqlalchemy import case, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.choice import ChoiceQuestion, ChoiceReason, ChoiceVote


async def list_questions(
    category: str | None,
    sort: str,
    db: AsyncSession,
) -> list[tuple[ChoiceQuestion, int]]:
    vote_count = func.count(ChoiceVote.id).label("vote_count")
    statement = (
        select(ChoiceQuestion, vote_count)
        .outerjoin(ChoiceVote, ChoiceVote.question_id == ChoiceQuestion.id)
        .where(ChoiceQuestion.is_active.is_(True))
        .group_by(ChoiceQuestion.id)
    )
    if category:
        statement = statement.where(ChoiceQuestion.category == category)
    if sort == "popular":
        statement = statement.order_by(vote_count.desc(), ChoiceQuestion.published_at.desc())
    else:
        statement = statement.order_by(ChoiceQuestion.published_at.desc())
    result = await db.execute(statement)
    return [(question, int(count)) for question, count in result.all()]


async def get_question(question_id: int, db: AsyncSession) -> ChoiceQuestion | None:
    result = await db.execute(
        select(ChoiceQuestion)
        .options(selectinload(ChoiceQuestion.reasons))
        .where(ChoiceQuestion.id == question_id, ChoiceQuestion.is_active.is_(True))
    )
    return result.scalar_one_or_none()


async def get_vote(
    question_id: int,
    user_id: int | None,
    guest_session_id: str,
    db: AsyncSession,
) -> ChoiceVote | None:
    identity_filter = (
        ChoiceVote.user_id == user_id
        if user_id is not None
        else ChoiceVote.guest_session_id == guest_session_id
    )
    result = await db.execute(
        select(ChoiceVote).where(
            ChoiceVote.question_id == question_id,
            identity_filter,
        )
    )
    return result.scalar_one_or_none()


async def list_votes_for_identity(
    user_id: int | None,
    guest_session_id: str,
    db: AsyncSession,
) -> list[ChoiceVote]:
    identity_filter = (
        ChoiceVote.user_id == user_id
        if user_id is not None
        else ChoiceVote.guest_session_id == guest_session_id
    )
    result = await db.execute(select(ChoiceVote).where(identity_filter))
    return list(result.scalars().all())


async def count_votes(question_id: int, db: AsyncSession) -> tuple[int, int]:
    result = await db.execute(
        select(
            func.sum(case((ChoiceVote.selected_option == "A", 1), else_=0)),
            func.sum(case((ChoiceVote.selected_option == "B", 1), else_=0)),
        ).where(ChoiceVote.question_id == question_id)
    )
    option_a, option_b = result.one()
    return int(option_a or 0), int(option_b or 0)


async def count_reasons(question_id: int, db: AsyncSession) -> dict[int, int]:
    result = await db.execute(
        select(ChoiceVote.reason_id, func.count(ChoiceVote.id))
        .where(ChoiceVote.question_id == question_id, ChoiceVote.reason_id.is_not(None))
        .group_by(ChoiceVote.reason_id)
    )
    return {int(reason_id): int(count) for reason_id, count in result.all()}


async def create_vote(
    question_id: int,
    selected_option: str,
    reason_id: int | None,
    user_id: int | None,
    guest_session_id: str,
    db: AsyncSession,
) -> ChoiceVote:
    vote = ChoiceVote(
        question_id=question_id,
        selected_option=selected_option,
        reason_id=reason_id,
        user_id=user_id,
        guest_session_id=None if user_id is not None else guest_session_id,
    )
    db.add(vote)
    await db.flush()
    return vote


async def list_user_votes(user_id: int, db: AsyncSession) -> list[ChoiceVote]:
    result = await db.execute(
        select(ChoiceVote)
        .options(
            selectinload(ChoiceVote.question).selectinload(ChoiceQuestion.reasons),
            selectinload(ChoiceVote.reason),
        )
        .where(ChoiceVote.user_id == user_id)
        .order_by(ChoiceVote.updated_at.desc())
    )
    return list(result.scalars().all())


async def delete_vote(vote_id: int, db: AsyncSession) -> None:
    await db.execute(delete(ChoiceVote).where(ChoiceVote.id == vote_id))
