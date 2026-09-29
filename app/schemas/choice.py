"""일상 선택 질문 API 스키마."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ChoiceCategory = Literal["work", "spending", "relationship", "daily"]
ChoiceOption = Literal["A", "B", "C", "D"]


class ChoiceReasonItem(BaseModel):
    id: int
    label: str


class ChoiceQuestionItem(BaseModel):
    id: int
    category: ChoiceCategory
    title: str
    option_a: str
    option_b: str
    option_c: str | None = None
    option_d: str | None = None
    is_daily: bool
    participant_count: int
    my_choice: ChoiceOption | None = None
    author_name: str
    created_at: datetime
    published_at: datetime


class ChoiceQuestionsResponse(BaseModel):
    items: list[ChoiceQuestionItem]


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


class MyChoiceItem(BaseModel):
    question: ChoiceQuestionItem
    selected_option: ChoiceOption
    reason: ChoiceReasonItem
    voted_at: datetime
