"""일상 선택 질문과 투표 DB 접근."""

from datetime import datetime

from sqlalchemy import and_, case, delete, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from app.models.choice import ChoiceLike, ChoiceQuestion, ChoiceReason, ChoiceVote


async def list_questions(
    category: list[str] | None,
    sort: str,
    db: AsyncSession,
    *,
    search: str = "",
    limit: int = 15,
    after: tuple[int, datetime, int] | None = None,
    user_id: int | None = None,
    scope: str = "all",
) -> list[tuple[ChoiceQuestion, int, int]]:
    vote_count = (
        select(func.count(ChoiceVote.id))
        .where(ChoiceVote.question_id == ChoiceQuestion.id)
        .correlate(ChoiceQuestion)
        .scalar_subquery()
        .label("vote_count")
    )
    like_count = (
        select(func.count(ChoiceLike.id))
        .where(ChoiceLike.question_id == ChoiceQuestion.id)
        .correlate(ChoiceQuestion)
        .scalar_subquery()
        .label("like_count")
    )
    statement = (
        select(ChoiceQuestion, vote_count, like_count)
        .options(selectinload(ChoiceQuestion.author))
        .where(ChoiceQuestion.is_active.is_(True))
    )
    if category:
        statement = statement.where(ChoiceQuestion.category.in_(category))
    if search:
        statement = statement.where(ChoiceQuestion.title.icontains(search, autoescape=True))
    if scope == "mine":
        statement = statement.where(select(ChoiceVote.id).where(
            ChoiceVote.question_id == ChoiceQuestion.id, ChoiceVote.user_id == user_id
        ).exists())
    elif scope == "liked":
        statement = statement.where(select(ChoiceLike.id).where(
            ChoiceLike.question_id == ChoiceQuestion.id, ChoiceLike.user_id == user_id
        ).exists())
    metric = vote_count if sort == "popular" else like_count if sort == "liked" else None
    if after is not None:
        count, published_at, question_id = after
        date_filter = or_(
            ChoiceQuestion.published_at < published_at,
            and_(ChoiceQuestion.published_at == published_at, ChoiceQuestion.id < question_id),
        )
        statement = statement.where(
            or_(metric < count, and_(metric == count, date_filter))
            if metric is not None else date_filter
        )
    if sort == "popular":
        statement = statement.order_by(
            vote_count.desc(),
            ChoiceQuestion.published_at.desc(),
            ChoiceQuestion.id.desc(),
        )
    elif sort == "liked":
        statement = statement.order_by(
            like_count.desc(),
            ChoiceQuestion.published_at.desc(),
            ChoiceQuestion.id.desc(),
        )
    else:
        statement = statement.order_by(
            ChoiceQuestion.published_at.desc(),
            ChoiceQuestion.id.desc(),
        )
    result = await db.execute(statement.limit(limit + 1))
    return [
        (question, int(participant_count), int(question_like_count))
        for question, participant_count, question_like_count in result.all()
    ]


async def get_question(question_id: int, db: AsyncSession) -> ChoiceQuestion | None:
    result = await db.execute(
        select(ChoiceQuestion)
        .options(
            selectinload(ChoiceQuestion.author),
            selectinload(ChoiceQuestion.reasons),
        )
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
    question_ids: list[int] | None = None,
) -> list[ChoiceVote]:
    identity_filter = (
        ChoiceVote.user_id == user_id
        if user_id is not None
        else ChoiceVote.guest_session_id == guest_session_id
    )
    result = await db.execute(select(ChoiceVote).where(
        identity_filter,
        ChoiceVote.question_id.in_(question_ids) if question_ids is not None else True,
    ))
    return list(result.scalars().all())


async def count_votes(question_id: int, db: AsyncSession) -> dict[str, int]:
    result = await db.execute(
        select(
            func.sum(case((ChoiceVote.selected_option == "A", 1), else_=0)),
            func.sum(case((ChoiceVote.selected_option == "B", 1), else_=0)),
            func.sum(case((ChoiceVote.selected_option == "C", 1), else_=0)),
            func.sum(case((ChoiceVote.selected_option == "D", 1), else_=0)),
        ).where(ChoiceVote.question_id == question_id)
    )
    option_a, option_b, option_c, option_d = result.one()
    return {
        "A": int(option_a or 0),
        "B": int(option_b or 0),
        "C": int(option_c or 0),
        "D": int(option_d or 0),
    }


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
    reason_id: int,
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


async def list_user_votes(user_id: int, db: AsyncSession, question_ids: list[int] | None = None) -> list[ChoiceVote]:
    result = await db.execute(
        select(ChoiceVote)
        .options(
            selectinload(ChoiceVote.question).selectinload(ChoiceQuestion.reasons),
            selectinload(ChoiceVote.question).selectinload(ChoiceQuestion.author),
            selectinload(ChoiceVote.reason),
        )
        .where(ChoiceVote.user_id == user_id,
               ChoiceVote.question_id.in_(question_ids) if question_ids is not None else True)
        .order_by(ChoiceVote.updated_at.desc())
    )
    return list(result.scalars().all())


async def delete_vote(vote_id: int, db: AsyncSession) -> None:
    await db.execute(delete(ChoiceVote).where(ChoiceVote.id == vote_id))


async def list_liked_question_ids(user_id: int, db: AsyncSession, question_ids: list[int] | None = None) -> set[int]:
    """사용자가 좋아요한 질문 ID를 조회한다."""
    result = await db.execute(
        select(ChoiceLike.question_id).where(
            ChoiceLike.user_id == user_id,
            ChoiceLike.question_id.in_(question_ids) if question_ids is not None else True,
        )
    )
    return set(result.scalars().all())


async def get_like(
    question_id: int,
    user_id: int,
    db: AsyncSession,
) -> ChoiceLike | None:
    """사용자의 질문 좋아요를 조회한다."""
    result = await db.execute(
        select(ChoiceLike).where(
            ChoiceLike.question_id == question_id,
            ChoiceLike.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_like(
    question_id: int,
    user_id: int,
    db: AsyncSession,
) -> ChoiceLike:
    """질문 좋아요를 추가한다."""
    like = ChoiceLike(question_id=question_id, user_id=user_id)
    db.add(like)
    await db.flush()
    return like


async def delete_like(like: ChoiceLike, db: AsyncSession) -> None:
    """질문 좋아요를 제거한다."""
    await db.delete(like)


async def count_likes(question_id: int, db: AsyncSession) -> int:
    """질문의 좋아요 수를 조회한다."""
    result = await db.execute(
        select(func.count(ChoiceLike.id)).where(ChoiceLike.question_id == question_id)
    )
    return int(result.scalar_one())


async def list_user_likes(user_id: int, db: AsyncSession, question_ids: list[int] | None = None) -> list[ChoiceLike]:
    """사용자가 좋아요한 질문을 최근 좋아요 순으로 조회한다."""
    result = await db.execute(
        select(ChoiceLike)
        .join(ChoiceLike.question)
        .options(
            selectinload(ChoiceLike.question).selectinload(ChoiceQuestion.author),
        )
        .where(
            ChoiceLike.user_id == user_id,
            ChoiceQuestion.is_active.is_(True),
            ChoiceLike.question_id.in_(question_ids) if question_ids is not None else True,
        )
        .order_by(ChoiceLike.created_at.desc())
    )
    return list(result.scalars().all())
