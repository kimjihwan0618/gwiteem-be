"""일상 선택 질문과 투표 비즈니스 로직."""

import base64
import binascii
import hashlib
import json

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidRequestException, NotFoundException
from app.models.choice import ChoiceQuestion, ChoiceVote
from app.repositories import choice_repo, comment_repo
from app.schemas.choice import (
    ChoiceQuestionDetail,
    ChoiceQuestionItem,
    ChoiceQuestionsResponse,
    ChoiceLikeResponse,
    ChoiceOptionResult,
    ChoiceReasonItem,
    ChoiceReasonResult,
    ChoiceResult,
    ChoiceVoteResponse,
    MyChoiceItem,
    MyLikedQuestionItem,
    QuestionCursor,
)
from app.schemas.common import CursorPage


async def _question_page(
    category: list[str] | None, sort: str, user_id: int | None, db: AsyncSession,
    search: str, limit: int, cursor: str | None, scope: str = "all",
) -> tuple[list[tuple[ChoiceQuestion, int, int]], str | None]:
    """필터에 결합된 커서로 필요한 질문만 조회한다."""
    search = search.strip()
    filters = hashlib.sha256(json.dumps(
        [sorted(category or []), sort, search, user_id, scope], ensure_ascii=False
    ).encode()).hexdigest()
    after = None
    if cursor:
        try:
            decoded = QuestionCursor.model_validate_json(base64.b64decode(
                cursor.encode("ascii"), altchars=b"-_", validate=True
            ))
        except (ValueError, ValidationError, binascii.Error, UnicodeError):
            raise InvalidRequestException("목록 커서가 올바르지 않습니다.") from None
        if decoded.filters != filters or decoded.published_at.tzinfo is not None:
            raise InvalidRequestException("검색 조건에 맞지 않는 목록 커서입니다.")
        after = (decoded.metric, decoded.published_at, decoded.question_id)
    rows = await choice_repo.list_questions(
        category, sort, db, search=search, limit=limit, after=after,
        user_id=user_id, scope=scope,
    )
    next_cursor = None
    if len(rows) > limit:
        question, votes, likes = rows[limit - 1]
        token = QuestionCursor(metric=votes if sort == "popular" else likes if sort == "liked" else 0,
                               published_at=question.published_at, question_id=question.id, filters=filters)
        next_cursor = base64.urlsafe_b64encode(token.model_dump_json().encode()).decode()
    return rows[:limit], next_cursor


def _question_item(
    question: ChoiceQuestion,
    participant_count: int,
    like_count: int,
    is_liked: bool,
    vote: ChoiceVote | None,
    comment_count: int,
) -> ChoiceQuestionItem:
    return ChoiceQuestionItem(
        id=question.id,
        category=question.category,
        title=question.title,
        option_a=question.option_a,
        option_b=question.option_b,
        option_c=question.option_c,
        option_d=question.option_d,
        is_daily=question.is_daily,
        participant_count=participant_count,
        like_count=like_count,
        comment_count=comment_count,
        is_liked=is_liked,
        my_choice=vote.selected_option if vote else None,
        author_name=question.author.nickname if question.author else "Gwiteem",
        created_at=question.created_at,
        published_at=question.published_at,
    )


async def list_questions(
    category: list[str] | None,
    sort: str,
    user_id: int | None,
    guest_session_id: str,
    db: AsyncSession,
    *,
    search: str = "",
    limit: int = 15,
    cursor: str | None = None,
) -> ChoiceQuestionsResponse:
    questions, next_cursor = await _question_page(category, sort, user_id, db, search, limit, cursor)
    question_ids = [q.id for q, _, _ in questions]
    comment_counts = await comment_repo.counts(question_ids, db)
    votes = await choice_repo.list_votes_for_identity(user_id, guest_session_id, db, question_ids)
    vote_by_question = {vote.question_id: vote for vote in votes}
    liked_question_ids = (
        await choice_repo.list_liked_question_ids(user_id, db, question_ids)
        if user_id is not None
        else set()
    )
    return ChoiceQuestionsResponse(
        next_cursor=next_cursor,
        items=[
            _question_item(
                question,
                participant_count,
                like_count,
                question.id in liked_question_ids,
                vote_by_question.get(question.id),
                comment_counts.get(question.id, 0),
            )
            for question, participant_count, like_count in questions
        ]
    )


async def _build_detail(
    question: ChoiceQuestion,
    vote: ChoiceVote | None,
    is_liked: bool,
    db: AsyncSession,
) -> ChoiceQuestionDetail:
    option_counts = await choice_repo.count_votes(question.id, db)
    total_count = sum(option_counts.values())
    reason_counts = await choice_repo.count_reasons(question.id, db)
    result = None
    if vote is not None:
        result = ChoiceResult(
            total_count=total_count,
            options=[
                ChoiceOptionResult(
                    option=option,
                    label=label,
                    count=option_counts[option],
                    percentage=round(option_counts[option] / total_count * 100, 1)
                    if total_count
                    else 0,
                )
                for option, label in _question_options(question)
            ],
            reasons=[
                ChoiceReasonResult(
                    id=reason.id,
                    label=reason.label,
                    count=reason_counts.get(reason.id, 0),
                    percentage=round(reason_counts.get(reason.id, 0) / total_count * 100, 1)
                    if total_count
                    else 0,
                )
                for reason in question.reasons
            ],
        )
    like_count = await choice_repo.count_likes(question.id, db)
    comment_count = (await comment_repo.counts([question.id], db)).get(question.id, 0)
    item = _question_item(question, total_count, like_count, is_liked, vote, comment_count)
    return ChoiceQuestionDetail(
        **item.model_dump(),
        reasons=[ChoiceReasonItem(id=reason.id, label=reason.label) for reason in question.reasons],
        my_reason_id=vote.reason_id if vote else None,
        result=result,
    )


async def get_question(
    question_id: int,
    user_id: int | None,
    guest_session_id: str,
    db: AsyncSession,
) -> ChoiceQuestionDetail:
    question = await choice_repo.get_question(question_id, db)
    if question is None:
        raise NotFoundException("질문을 찾을 수 없습니다.")
    vote = await choice_repo.get_vote(question_id, user_id, guest_session_id, db)
    is_liked = (
        await choice_repo.get_like(question_id, user_id, db) is not None
        if user_id is not None
        else False
    )
    return await _build_detail(question, vote, is_liked, db)


async def vote(
    question_id: int,
    selected_option: str,
    reason_id: int,
    user_id: int | None,
    guest_session_id: str,
    db: AsyncSession,
) -> ChoiceVoteResponse:
    question = await choice_repo.get_question(question_id, db)
    if question is None:
        raise NotFoundException("질문을 찾을 수 없습니다.")
    if selected_option not in {option for option, _ in _question_options(question)}:
        raise InvalidRequestException("선택한 항목이 이 질문에 존재하지 않습니다.")
    if reason_id not in {reason.id for reason in question.reasons}:
        raise InvalidRequestException("선택한 이유가 이 질문에 속하지 않습니다.")

    existing = await choice_repo.get_vote(question_id, user_id, guest_session_id, db)
    if existing is None:
        existing = await choice_repo.create_vote(
            question_id,
            selected_option,
            reason_id,
            user_id,
            guest_session_id,
            db,
        )
    else:
        existing.selected_option = selected_option
        existing.reason_id = reason_id
    await db.commit()
    await db.refresh(existing)
    is_liked = (
        await choice_repo.get_like(question_id, user_id, db) is not None
        if user_id is not None
        else False
    )
    return ChoiceVoteResponse(
        question=await _build_detail(question, existing, is_liked, db)
    )


async def migrate_guest_votes(
    guest_session_id: str,
    user_id: int,
    db: AsyncSession,
) -> int:
    guest_votes = await choice_repo.list_votes_for_identity(None, guest_session_id, db)
    user_votes = await choice_repo.list_votes_for_identity(user_id, guest_session_id, db)
    user_question_ids = {vote.question_id for vote in user_votes}
    migrated_count = 0
    for guest_vote in guest_votes:
        if guest_vote.question_id in user_question_ids:
            await choice_repo.delete_vote(guest_vote.id, db)
            continue
        guest_vote.user_id = user_id
        guest_vote.guest_session_id = None
        migrated_count += 1
    await db.commit()
    return migrated_count


async def list_my_choices(
    user_id: int, db: AsyncSession, *, category: list[str] | None = None,
    sort: str = "popular", search: str = "", limit: int = 15, cursor: str | None = None,
) -> CursorPage[MyChoiceItem]:
    rows, next_cursor = await _question_page(category, sort, user_id, db, search, limit, cursor, "mine")
    question_ids = [q.id for q, _, _ in rows]
    votes = await choice_repo.list_user_votes(user_id, db, question_ids)
    votes.sort(key=lambda vote: question_ids.index(vote.question_id))
    metrics = {q.id: (votes, likes) for q, votes, likes in rows}
    liked_question_ids = await choice_repo.list_liked_question_ids(user_id, db, question_ids)
    comment_counts = await comment_repo.counts([vote.question_id for vote in votes], db)
    items: list[MyChoiceItem] = []
    for vote in votes:
        participant_count, like_count = metrics[vote.question_id]
        items.append(
            MyChoiceItem(
                question=_question_item(
                    vote.question,
                    participant_count,
                    like_count,
                    vote.question_id in liked_question_ids,
                    vote,
                    comment_counts.get(vote.question_id, 0),
                ),
                selected_option=vote.selected_option,
                reason=ChoiceReasonItem(id=vote.reason.id, label=vote.reason.label),
                voted_at=vote.updated_at,
            )
        )
    return CursorPage(items=items, next_cursor=next_cursor)


async def set_like(
    question_id: int,
    user_id: int,
    is_liked: bool,
    db: AsyncSession,
) -> ChoiceLikeResponse:
    """로그인 사용자의 질문 좋아요 상태를 멱등하게 변경한다."""
    question = await choice_repo.get_question(question_id, db)
    if question is None:
        raise NotFoundException("질문을 찾을 수 없습니다.")

    existing = await choice_repo.get_like(question_id, user_id, db)
    if is_liked and existing is None:
        await choice_repo.create_like(question_id, user_id, db)
    elif not is_liked and existing is not None:
        await choice_repo.delete_like(existing, db)
    await db.commit()

    return ChoiceLikeResponse(
        question_id=question_id,
        is_liked=is_liked,
        like_count=await choice_repo.count_likes(question_id, db),
    )


async def list_my_liked_questions(
    user_id: int,
    db: AsyncSession,
    *, category: list[str] | None = None, sort: str = "popular",
    search: str = "", limit: int = 15, cursor: str | None = None,
) -> CursorPage[MyLikedQuestionItem]:
    """로그인 사용자가 좋아요한 질문 목록을 반환한다."""
    rows, next_cursor = await _question_page(category, sort, user_id, db, search, limit, cursor, "liked")
    question_ids = [q.id for q, _, _ in rows]
    likes = await choice_repo.list_user_likes(user_id, db, question_ids)
    likes.sort(key=lambda like: question_ids.index(like.question_id))
    metrics = {q.id: (votes, likes) for q, votes, likes in rows}
    votes = await choice_repo.list_votes_for_identity(user_id, "", db, question_ids)
    vote_by_question = {vote.question_id: vote for vote in votes}
    comment_counts = await comment_repo.counts([like.question_id for like in likes], db)
    items: list[MyLikedQuestionItem] = []
    for like in likes:
        participant_count, like_count = metrics[like.question_id]
        items.append(
            MyLikedQuestionItem(
                question=_question_item(
                    like.question,
                    participant_count,
                    like_count,
                    True,
                    vote_by_question.get(like.question_id),
                    comment_counts.get(like.question_id, 0),
                ),
                liked_at=like.created_at,
            )
        )
    return CursorPage(items=items, next_cursor=next_cursor)


def _question_options(question: ChoiceQuestion) -> list[tuple[str, str]]:
    """질문에 실제 등록된 선택지를 순서대로 반환한다."""
    options = [
        ("A", question.option_a),
        ("B", question.option_b),
        ("C", question.option_c),
        ("D", question.option_d),
    ]
    return [(option, label) for option, label in options if label is not None]
