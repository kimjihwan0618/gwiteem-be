"""일상 선택 질문과 투표 비즈니스 로직."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidRequestException, NotFoundException
from app.models.choice import ChoiceQuestion, ChoiceVote
from app.repositories import choice_repo
from app.schemas.choice import (
    ChoiceQuestionDetail,
    ChoiceQuestionItem,
    ChoiceQuestionsResponse,
    ChoiceReasonItem,
    ChoiceReasonResult,
    ChoiceResult,
    ChoiceVoteResponse,
    MyChoiceItem,
)


def _question_item(
    question: ChoiceQuestion,
    participant_count: int,
    vote: ChoiceVote | None,
) -> ChoiceQuestionItem:
    return ChoiceQuestionItem(
        id=question.id,
        category=question.category,
        title=question.title,
        option_a=question.option_a,
        option_b=question.option_b,
        is_daily=question.is_daily,
        participant_count=participant_count,
        my_choice=vote.selected_option if vote else None,
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
    return ChoiceQuestionsResponse(
        items=[
            _question_item(question, count, vote_by_question.get(question.id))
            for question, count in questions
        ]
    )


async def _build_detail(
    question: ChoiceQuestion,
    vote: ChoiceVote | None,
    db: AsyncSession,
) -> ChoiceQuestionDetail:
    option_a_count, option_b_count = await choice_repo.count_votes(question.id, db)
    total_count = option_a_count + option_b_count
    reason_counts = await choice_repo.count_reasons(question.id, db)
    result = None
    if vote is not None:
        result = ChoiceResult(
            total_count=total_count,
            option_a_count=option_a_count,
            option_b_count=option_b_count,
            option_a_percentage=round(option_a_count / total_count * 100, 1)
            if total_count
            else 0,
            option_b_percentage=round(option_b_count / total_count * 100, 1)
            if total_count
            else 0,
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
    item = _question_item(question, total_count, vote)
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
    return await _build_detail(question, vote, db)


async def vote(
    question_id: int,
    selected_option: str,
    reason_id: int | None,
    user_id: int | None,
    guest_session_id: str,
    db: AsyncSession,
) -> ChoiceVoteResponse:
    question = await choice_repo.get_question(question_id, db)
    if question is None:
        raise NotFoundException("질문을 찾을 수 없습니다.")
    if reason_id is not None and reason_id not in {reason.id for reason in question.reasons}:
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
    return ChoiceVoteResponse(question=await _build_detail(question, existing, db))


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
    items: list[MyChoiceItem] = []
    for vote in votes:
        option_a_count, option_b_count = await choice_repo.count_votes(vote.question_id, db)
        items.append(
            MyChoiceItem(
                question=_question_item(
                    vote.question, option_a_count + option_b_count, vote
                ),
                selected_option=vote.selected_option,
                reason=ChoiceReasonItem(id=vote.reason.id, label=vote.reason.label)
                if vote.reason
                else None,
                voted_at=vote.updated_at,
            )
        )
    return items
