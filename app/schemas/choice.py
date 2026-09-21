"""일상 선택 질문 API 스키마."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


ChoiceCategory = Literal["work", "spending", "relationship", "daily"]
ChoiceOption = Literal["A", "B"]


class ChoiceReasonItem(BaseModel):
    id: int
    label: str


class ChoiceQuestionItem(BaseModel):
    id: int
    category: ChoiceCategory
    title: str
    option_a: str
    option_b: str
    is_daily: bool
    participant_count: int
    my_choice: ChoiceOption | None = None
    published_at: datetime


class ChoiceQuestionsResponse(BaseModel):
    items: list[ChoiceQuestionItem]


class ChoiceReasonResult(BaseModel):
    id: int
    label: str
    count: int
    percentage: float


class ChoiceResult(BaseModel):
    total_count: int
    option_a_count: int
    option_b_count: int
    option_a_percentage: float
    option_b_percentage: float
    reasons: list[ChoiceReasonResult]


class ChoiceQuestionDetail(ChoiceQuestionItem):
    reasons: list[ChoiceReasonItem]
    my_reason_id: int | None = None
    result: ChoiceResult | None = None


class ChoiceVoteRequest(BaseModel):
    selected_option: ChoiceOption
    reason_id: int | None = Field(default=None, ge=1)


class ChoiceVoteResponse(BaseModel):
    question: ChoiceQuestionDetail


class ChoiceVoteMigrationResponse(BaseModel):
    migrated_count: int


class MyChoiceItem(BaseModel):
    question: ChoiceQuestionItem
    selected_option: ChoiceOption
    reason: ChoiceReasonItem | None
    voted_at: datetime
