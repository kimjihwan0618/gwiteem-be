"""일상 선택 질문과 투표 비즈니스 로직."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidRequestException, NotFoundException
from app.models.choice import ChoiceQuestion, ChoiceVote
from app.repositories import choice_repo
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
)


def _question_item(
    question: ChoiceQuestion,
    participant_count: int,
    like_count: int,
    is_liked: bool,
    vote: ChoiceVote | None,
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
        is_liked=is_liked,
        my_choice=vote.selected_option if vote else None,
        author_name=question.author.nickname if question.author else "Gwiteem",
        created_at=question.created_at,
        published_at=question.published_at,
    )


async def list_questions(
    category: str | None,
    sort: str,
    user_id: int | None,
    guest_session_id: str,
    db: AsyncSession,
) -> ChoiceQuestionsResponse:
    questions = await choice_repo.list_questions(category, sort, db)
    votes = await choice_repo.list_votes_for_identity(user_id, guest_session_id, db)
    vote_by_question = {vote.question_id: vote for vote in votes}
    liked_question_ids = (
        await choice_repo.list_liked_question_ids(user_id, db)
        if user_id is not None
        else set()
    )
    return ChoiceQuestionsResponse(
        items=[
            _question_item(
                question,
                participant_count,
                like_count,
                question.id in liked_question_ids,
                vote_by_question.get(question.id),
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
    item = _question_item(question, total_count, like_count, is_liked, vote)
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


async def list_my_choices(user_id: int, db: AsyncSession) -> list[MyChoiceItem]:
    votes = await choice_repo.list_user_votes(user_id, db)
    liked_question_ids = await choice_repo.list_liked_question_ids(user_id, db)
    items: list[MyChoiceItem] = []
    for vote in votes:
        option_counts = await choice_repo.count_votes(vote.question_id, db)
        like_count = await choice_repo.count_likes(vote.question_id, db)
        items.append(
            MyChoiceItem(
                question=_question_item(
                    vote.question,
                    sum(option_counts.values()),
                    like_count,
                    vote.question_id in liked_question_ids,
                    vote,
                ),
                selected_option=vote.selected_option,
                reason=ChoiceReasonItem(id=vote.reason.id, label=vote.reason.label),
                voted_at=vote.updated_at,
            )
        )
    return items


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
) -> list[MyLikedQuestionItem]:
    """로그인 사용자가 좋아요한 질문 목록을 반환한다."""
    likes = await choice_repo.list_user_likes(user_id, db)
    votes = await choice_repo.list_votes_for_identity(user_id, "", db)
    vote_by_question = {vote.question_id: vote for vote in votes}
    items: list[MyLikedQuestionItem] = []
    for like in likes:
        option_counts = await choice_repo.count_votes(like.question_id, db)
        like_count = await choice_repo.count_likes(like.question_id, db)
        items.append(
            MyLikedQuestionItem(
                question=_question_item(
                    like.question,
                    sum(option_counts.values()),
                    like_count,
                    True,
                    vote_by_question.get(like.question_id),
                ),
                liked_at=like.created_at,
            )
        )
    return items


def _question_options(question: ChoiceQuestion) -> list[tuple[str, str]]:
    """질문에 실제 등록된 선택지를 순서대로 반환한다."""
    options = [
        ("A", question.option_a),
        ("B", question.option_b),
        ("C", question.option_c),
        ("D", question.option_d),
    ]
    return [(option, label) for option, label in options if label is not None]
