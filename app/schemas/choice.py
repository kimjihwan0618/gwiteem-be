"""일상 선택 질문 API 스키마."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from app.core.choice_categories import ChoiceCategory, CreationCategory
from app.schemas.common import CursorPage


ChoiceOption = Literal["A", "B", "C", "D"]


class CreateQuestionRequest(BaseModel):
    """작성자는 인증 사용자로 결정하고 운영 플래그는 입력받지 않는다."""
    model_config = ConfigDict(extra="forbid")
    category: CreationCategory
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=200)]
    options: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]] = Field(min_length=2, max_length=4)
    reasons: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]] = Field(min_length=2, max_length=6)

    @field_validator("options", "reasons")
    @classmethod
    def unique_labels(cls, values: list[str]) -> list[str]:
        if len({value.casefold() for value in values}) != len(values):
            raise ValueError("중복된 항목을 입력할 수 없습니다.")
        return values


class QuestionListParams(BaseModel):
    """질문 목록의 서버 검색과 페이지 크기 제한."""

    category: list[ChoiceCategory] = Field(default_factory=list)
    sort: Literal["popular", "latest", "liked"] = "popular"
    q: str = Field(default="", max_length=200)
    limit: int = Field(default=15, ge=1, le=15)
    cursor: str | None = Field(default=None, max_length=2048)


class ChoiceReasonItem(BaseModel):
    id: int
    label: str


class ChoiceQuestionItem(BaseModel):
    id: int
    category: str
    category_label: str
    title: str
    option_a: str
    option_b: str
    option_c: str | None = None
    option_d: str | None = None
    is_daily: bool
    participant_count: int
    like_count: int
    comment_count: int
    is_liked: bool
    my_choice: ChoiceOption | None = None
    author_name: str
    created_at: datetime
    published_at: datetime


class ChoiceQuestionsResponse(CursorPage[ChoiceQuestionItem]):
    pass


class QuestionCursor(BaseModel):
    """정렬 조건과 마지막 항목을 담는 목록 커서."""

    metric: int = Field(ge=0)
    published_at: datetime
    question_id: int = Field(ge=1)
    filters: str


class ChoiceReasonResult(BaseModel):
    id: int
    label: str
    count: int
    percentage: float


class ChoiceOptionResult(BaseModel):
    option: ChoiceOption
    label: str
    count: int
    percentage: float


class ChoiceResult(BaseModel):
    total_count: int
    options: list[ChoiceOptionResult]
    reasons: list[ChoiceReasonResult]


class ChoiceQuestionDetail(ChoiceQuestionItem):
    reasons: list[ChoiceReasonItem]
    my_reason_id: int | None = None
    result: ChoiceResult | None = None


class ChoiceVoteRequest(BaseModel):
    selected_option: ChoiceOption
    reason_id: int = Field(ge=1)


class ChoiceVoteResponse(BaseModel):
    question: ChoiceQuestionDetail


class ChoiceVoteMigrationResponse(BaseModel):
    migrated_count: int


class ChoiceLikeResponse(BaseModel):
    question_id: int
    is_liked: bool
    like_count: int


class MyChoiceItem(BaseModel):
    question: ChoiceQuestionItem
    selected_option: ChoiceOption
    reason: ChoiceReasonItem
    voted_at: datetime


class MyLikedQuestionItem(BaseModel):
    question: ChoiceQuestionItem
    liked_at: datetime
