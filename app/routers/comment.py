"""질문별 댓글 API. 조회는 공개, 변경은 로그인 필수."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.deps import get_current_user, get_optional_user, get_db
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.comment import CommentPage, CommentWrite, CommentMutation, CommentResponse
from app.services import comment_service

router = APIRouter(prefix="/questions/{question_id}/comments")


@router.post("/{comment_id}/replies", response_model=CommentResponse, status_code=201)
async def create_reply(question_id: int, comment_id: int, body: CommentWrite, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CommentResponse:
    reply_id = await comment_service.create_reply(question_id, comment_id, user.id, body.content, db)
    return CommentResponse(data=CommentMutation(id=reply_id), message="답글을 등록했습니다.")


@router.patch("/{comment_id}/replies/{reply_id}", response_model=CommentResponse)
async def edit_reply(question_id: int, comment_id: int, reply_id: int, body: CommentWrite, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CommentResponse:
    await comment_service.mutate_reply(question_id, comment_id, reply_id, user.id, body.content, db)
    return CommentResponse(data=CommentMutation(id=reply_id), message="답글을 수정했습니다.")


@router.delete("/{comment_id}/replies/{reply_id}", response_model=CommentResponse)
async def remove_reply(question_id: int, comment_id: int, reply_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CommentResponse:
    await comment_service.mutate_reply(question_id, comment_id, reply_id, user.id, None, db)
    return CommentResponse(data=CommentMutation(id=reply_id), message="답글을 삭제했습니다.")


@router.get("", response_model=ApiResponse[CommentPage])
async def list_comments(question_id: int, cursor: int | None = Query(None, ge=1), user: User | None = Depends(get_optional_user), db: AsyncSession = Depends(get_db)) -> ApiResponse[CommentPage]:
    return ApiResponse(data=await comment_service.list_comments(question_id, user.id if user else None, cursor, db))


@router.post("", response_model=CommentResponse, status_code=201)
async def create(question_id: int, body: CommentWrite, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CommentResponse:
    comment_id = await comment_service.create(question_id, user.id, body.content, db)
    return CommentResponse(data=CommentMutation(id=comment_id), message="댓글을 등록했습니다.")


@router.patch("/{comment_id}", response_model=CommentResponse)
async def edit(question_id: int, comment_id: int, body: CommentWrite, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CommentResponse:
    await comment_service.mutate(question_id, comment_id, user.id, "edit", body.content, db)
    return CommentResponse(data=CommentMutation(id=comment_id), message="댓글을 수정했습니다.")


@router.delete("/{comment_id}", response_model=CommentResponse)
async def remove(question_id: int, comment_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CommentResponse:
    await comment_service.mutate(question_id, comment_id, user.id, "delete", None, db)
    return CommentResponse(data=CommentMutation(id=comment_id), message="댓글을 삭제했습니다.")


@router.put("/{comment_id}/like", response_model=CommentResponse)
async def like(question_id: int, comment_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CommentResponse:
    await comment_service.mutate(question_id, comment_id, user.id, "like", None, db)
    return CommentResponse(data=CommentMutation(id=comment_id), message="댓글에 좋아요를 남겼습니다.")


@router.delete("/{comment_id}/like", response_model=CommentResponse)
async def unlike(question_id: int, comment_id: int, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> CommentResponse:
    await comment_service.mutate(question_id, comment_id, user.id, "unlike", None, db)
    return CommentResponse(data=CommentMutation(id=comment_id), message="댓글 좋아요를 취소했습니다.")
