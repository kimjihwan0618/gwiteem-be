"""댓글 공개 조회 및 작성자 권한 검사."""
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exceptions import ForbiddenException, NotFoundException, InvalidRequestException
from app.repositories import choice_repo, comment_repo
from app.schemas.comment import CommentItem, CommentPage, ReplyItem


async def require_question(question_id: int, db: AsyncSession) -> None:
    if await choice_repo.get_question(question_id, db) is None:
        raise NotFoundException("질문을 찾을 수 없습니다.")


async def list_comments(question_id: int, user_id: int | None, cursor: int | None, db: AsyncSession) -> CommentPage:
    await require_question(question_id, db)
    rows = await comment_repo.list_comments(question_id, user_id, cursor, db)
    replies = await comment_repo.list_replies([c.id for c, _, _ in rows[:20]], db)
    replies_by_comment: dict[int, list[ReplyItem]] = {}
    for reply in replies:
        replies_by_comment.setdefault(reply.comment_id, []).append(ReplyItem(
            id=reply.id, content=reply.content, author_name=reply.author.nickname,
            avatar_url=reply.author.profile_image_url, is_mine=reply.user_id == user_id,
            created_at=reply.created_at, updated_at=reply.updated_at,
        ))
    return CommentPage(items=[CommentItem(
        id=c.id, content=c.content, author_name=c.author.nickname,
        avatar_url=c.author.profile_image_url, is_mine=c.user_id == user_id,
        created_at=c.created_at, updated_at=c.updated_at,
        like_count=count, is_liked=liked, replies=replies_by_comment.get(c.id, []),
    ) for c, count, liked in rows[:20]],
        next_cursor=rows[19][0].id if len(rows) > 20 else None,
        total_count=(await comment_repo.counts([question_id], db)).get(question_id, 0))


async def create(question_id: int, user_id: int, content: str, db: AsyncSession) -> int:
    await require_question(question_id, db)
    comment = await comment_repo.create(question_id, user_id, content, db)
    comment_id = comment.id
    await db.commit()
    return comment_id


async def create_reply(question_id: int, comment_id: int, user_id: int, content: str, db: AsyncSession) -> int:
    await require_question(question_id, db)
    if await comment_repo.get_comment(question_id, comment_id, db) is None:
        raise NotFoundException("댓글을 찾을 수 없습니다.")
    reply = await comment_repo.create_reply(comment_id, user_id, content, db)
    reply_id = reply.id
    await db.commit()
    return reply_id


async def mutate_reply(question_id: int, comment_id: int, reply_id: int, user_id: int, content: str | None, db: AsyncSession) -> None:
    await require_question(question_id, db)
    if await comment_repo.get_comment(question_id, comment_id, db) is None:
        raise NotFoundException("댓글을 찾을 수 없습니다.")
    reply = await comment_repo.get_reply(comment_id, reply_id, db)
    if reply is None:
        raise NotFoundException("답글을 찾을 수 없습니다.")
    if reply.user_id != user_id:
        raise ForbiddenException("본인이 작성한 답글만 변경할 수 있습니다.")
    if content is None:
        await comment_repo.remove_reply(reply, db)
    else:
        await comment_repo.update_reply(reply, content, db)
    await db.commit()


async def mutate(question_id: int, comment_id: int, user_id: int, action: str, content: str | None, db: AsyncSession) -> None:
    await require_question(question_id, db)
    comment = await comment_repo.get_comment(question_id, comment_id, db)
    if comment is None:
        raise NotFoundException("댓글을 찾을 수 없습니다.")
    if action in {"edit", "delete"} and comment.user_id != user_id:
        raise ForbiddenException("본인이 작성한 댓글만 변경할 수 있습니다.")
    if action == "edit":
        if content is None:
            raise InvalidRequestException("댓글 내용을 입력해 주세요.")
        await comment_repo.update(comment, content, db)
    elif action == "delete":
        await comment_repo.remove(comment, db)
    else:
        await comment_repo.set_like(comment_id, user_id, action == "like", db)
    await db.commit()
