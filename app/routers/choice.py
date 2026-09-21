"""일상 선택 질문 API 라우터."""

from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, get_db, get_guest_session_id, get_optional_user
from app.models.user import User
from app.schemas.choice import (
    ChoiceQuestionDetail,
    ChoiceQuestionsResponse,
    ChoiceVoteMigrationResponse,
    ChoiceVoteRequest,
    ChoiceVoteResponse,
    MyChoiceItem,
)
from app.schemas.common import ApiResponse
from app.services import choice_service

router = APIRouter(prefix="/choices", tags=["choices"])


@router.get("/questions", response_model=ApiResponse[ChoiceQuestionsResponse])
async def list_questions(
    category: Literal["work", "spending", "relationship", "daily"] | None = Query(default=None),
    sort: Literal["popular", "latest"] = Query(default="popular"),
    current_user: User | None = Depends(get_optional_user),
    guest_session_id: str = Depends(get_guest_session_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ChoiceQuestionsResponse]:
    """활성 질문 목록. 인증: Optional."""
    data = await choice_service.list_questions(
        category,
        sort,
        current_user.id if current_user else None,
        guest_session_id,
        db,
    )
    return ApiResponse(success=True, data=data)


@router.get("/questions/{question_id}", response_model=ApiResponse[ChoiceQuestionDetail])
async def get_question(
    question_id: int,
    current_user: User | None = Depends(get_optional_user),
    guest_session_id: str = Depends(get_guest_session_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ChoiceQuestionDetail]:
    """질문 상세와 투표 후 결과. 인증: Optional."""
    data = await choice_service.get_question(
        question_id,
        current_user.id if current_user else None,
        guest_session_id,
        db,
    )
    return ApiResponse(success=True, data=data)


@router.post(
    "/questions/{question_id}/votes",
    response_model=ApiResponse[ChoiceVoteResponse],
)
async def vote(
    question_id: int,
    body: ChoiceVoteRequest,
    current_user: User | None = Depends(get_optional_user),
    guest_session_id: str = Depends(get_guest_session_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ChoiceVoteResponse]:
    """질문에 투표하거나 기존 선택을 변경. 인증: Optional."""
    data = await choice_service.vote(
        question_id,
        body.selected_option,
        body.reason_id,
        current_user.id if current_user else None,
        guest_session_id,
        db,
    )
    return ApiResponse(success=True, data=data)


@router.post(
    "/votes/migrate",
    response_model=ApiResponse[ChoiceVoteMigrationResponse],
)
async def migrate_votes(
    current_user: User = Depends(get_current_user),
    guest_session_id: str = Depends(get_guest_session_id),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[ChoiceVoteMigrationResponse]:
    """현재 브라우저의 게스트 선택을 로그인 계정에 병합. 인증: Required."""
    migrated_count = await choice_service.migrate_guest_votes(
        guest_session_id, current_user.id, db
    )
    return ApiResponse(
        success=True,
        data=ChoiceVoteMigrationResponse(migrated_count=migrated_count),
    )


@router.get("/me", response_model=ApiResponse[list[MyChoiceItem]])
async def list_my_choices(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse[list[MyChoiceItem]]:
    """로그인 사용자의 선택 기록. 인증: Required."""
    data = await choice_service.list_my_choices(current_user.id, db)
    return ApiResponse(success=True, data=data)
