"""일상 선택 질문, 선택 이유, 사용자 투표 모델."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class ChoiceQuestion(Base):
    """사용자에게 노출할 2~4개 선택지 질문."""

    __tablename__ = "choice_questions"
    __table_args__ = (
        CheckConstraint(
            "option_d IS NULL OR option_c IS NOT NULL",
            name="ck_choice_questions_option_order",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    author_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    category: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str] = mapped_column(String(200))
    option_a: Mapped[str] = mapped_column(String(100))
    option_b: Mapped[str] = mapped_column(String(100))
    option_c: Mapped[str | None] = mapped_column(String(100), nullable=True)
    option_d: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_daily: Mapped[bool] = mapped_column(default=False, index=True)
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    author: Mapped["User | None"] = relationship()
    reasons: Mapped[list["ChoiceReason"]] = relationship(
        back_populates="question", cascade="all, delete-orphan", order_by="ChoiceReason.sort_order"
    )
    votes: Mapped[list["ChoiceVote"]] = relationship(
        back_populates="question", cascade="all, delete-orphan"
    )


class ChoiceReason(Base):
    """질문에 답한 사용자가 선택할 수 있는 이유."""

    __tablename__ = "choice_reasons"

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("choice_questions.id", ondelete="CASCADE"), index=True
    )
    label: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    question: Mapped["ChoiceQuestion"] = relationship(back_populates="reasons")


class ChoiceVote(Base):
    """회원 또는 게스트의 질문별 단일 투표."""

    __tablename__ = "choice_votes"
    __table_args__ = (
        CheckConstraint(
            "selected_option IN ('A', 'B', 'C', 'D')",
            name="ck_choice_votes_option",
        ),
        CheckConstraint(
            "(user_id IS NOT NULL AND guest_session_id IS NULL) OR "
            "(user_id IS NULL AND guest_session_id IS NOT NULL)",
            name="ck_choice_votes_participant",
        ),
        Index(
            "uq_choice_votes_question_user",
            "question_id",
            "user_id",
            unique=True,
            postgresql_where=text("user_id IS NOT NULL"),
        ),
        Index(
            "uq_choice_votes_question_guest",
            "question_id",
            "guest_session_id",
            unique=True,
            postgresql_where=text("guest_session_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(
        ForeignKey("choice_questions.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True
    )
    guest_session_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    selected_option: Mapped[str] = mapped_column(String(1))
    reason_id: Mapped[int] = mapped_column(
        ForeignKey("choice_reasons.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    question: Mapped["ChoiceQuestion"] = relationship(back_populates="votes")
    reason: Mapped["ChoiceReason"] = relationship()
