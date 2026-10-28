"""댓글 DB 접근과 동시 수정 직렬화."""
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from app.models.comment import ChoiceComment, ChoiceCommentLike, ChoiceReply


async def counts(question_ids: list[int], db: AsyncSession) -> dict[int, int]:
    rows = await db.execute(select(ChoiceComment.question_id, func.count(ChoiceComment.id)).where(
        ChoiceComment.question_id.in_(question_ids)).group_by(ChoiceComment.question_id))
    return dict(rows.all())


async def list_comments(question_id: int, user_id: int | None, cursor: int | None, db: AsyncSession) -> list[tuple[ChoiceComment, int, bool]]:
    likes = select(func.count(ChoiceCommentLike.id)).where(ChoiceCommentLike.comment_id == ChoiceComment.id).correlate(ChoiceComment).scalar_subquery()
    mine = select(ChoiceCommentLike.id).where(ChoiceCommentLike.comment_id == ChoiceComment.id, ChoiceCommentLike.user_id == user_id).correlate(ChoiceComment).exists()
    query = select(ChoiceComment, likes, mine).options(selectinload(ChoiceComment.author)).where(ChoiceComment.question_id == question_id)
    if cursor is not None:
        query = query.where(ChoiceComment.id < cursor)
    rows = await db.execute(query.order_by(ChoiceComment.id.desc()).limit(21))
    return list(rows.all())


async def get_comment(question_id: int, comment_id: int, db: AsyncSession) -> ChoiceComment | None:
    rows = await db.execute(select(ChoiceComment).where(ChoiceComment.id == comment_id, ChoiceComment.question_id == question_id).with_for_update())
    return rows.scalar_one_or_none()


async def create(question_id: int, user_id: int, content: str, db: AsyncSession) -> ChoiceComment:
    comment = ChoiceComment(question_id=question_id, user_id=user_id, content=content)
    db.add(comment)
    await db.flush()
    return comment


async def update(comment: ChoiceComment, content: str, db: AsyncSession) -> None:
    comment.content = content
    await db.flush()


async def remove(comment: ChoiceComment, db: AsyncSession) -> None:
    await db.delete(comment)


async def set_like(comment_id: int, user_id: int, liked: bool, db: AsyncSession) -> None:
    query = select(ChoiceCommentLike).where(ChoiceCommentLike.comment_id == comment_id, ChoiceCommentLike.user_id == user_id)
    existing = (await db.execute(query)).scalar_one_or_none()
    if liked and existing is None:
        db.add(ChoiceCommentLike(comment_id=comment_id, user_id=user_id))
    elif not liked and existing is not None:
        await db.delete(existing)


async def list_replies(comment_ids: list[int], db: AsyncSession) -> list[ChoiceReply]:
    rows = await db.execute(
        select(ChoiceReply).options(selectinload(ChoiceReply.author))
        .where(ChoiceReply.comment_id.in_(comment_ids))
        .order_by(ChoiceReply.created_at, ChoiceReply.id)
    )
    return list(rows.scalars().all())


async def create_reply(comment_id: int, user_id: int, content: str, db: AsyncSession) -> ChoiceReply:
    reply = ChoiceReply(comment_id=comment_id, user_id=user_id, content=content)
    db.add(reply)
    await db.flush()
    return reply


async def get_reply(comment_id: int, reply_id: int, db: AsyncSession) -> ChoiceReply | None:
    rows = await db.execute(select(ChoiceReply).where(
        ChoiceReply.id == reply_id, ChoiceReply.comment_id == comment_id,
    ).with_for_update())
    return rows.scalar_one_or_none()


async def update_reply(reply: ChoiceReply, content: str, db: AsyncSession) -> None:
    reply.content = content
    await db.flush()


async def remove_reply(reply: ChoiceReply, db: AsyncSession) -> None:
    await db.delete(reply)
