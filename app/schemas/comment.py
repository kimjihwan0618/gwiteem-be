"""댓글 요청과 응답 계약."""
from datetime import datetime
from pydantic import BaseModel, Field, field_validator
from app.schemas.common import ApiResponse


class CommentWrite(BaseModel):
    content: str = Field(min_length=1, max_length=1000)

    @field_validator("content", mode="before")
    @classmethod
    def strip_content(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


class ReplyItem(BaseModel):
    id: int
    content: str
    author_name: str
    avatar_url: str | None
    is_mine: bool
    created_at: datetime
    updated_at: datetime


class CommentItem(ReplyItem):
    like_count: int
    is_liked: bool
    replies: list[ReplyItem] = Field(default_factory=list)


class CommentPage(BaseModel):
    items: list[CommentItem]
    next_cursor: int | None
    total_count: int


class CommentMutation(BaseModel):
    id: int


class CommentResponse(ApiResponse[CommentMutation]):
    message: str
