"""질문별 댓글과 댓글 좋아요 모델."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class ChoiceComment(Base):
    __tablename__ = "choice_comments"
    __table_args__ = (
        CheckConstraint("length(trim(content)) BETWEEN 1 AND 1000", name="ck_choice_comments_content"),
        Index("ix_choice_comments_question_id_id", "question_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    question_id: Mapped[int] = mapped_column(ForeignKey("choice_questions.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    author: Mapped[User] = relationship()


class ChoiceCommentLike(Base):
    __tablename__ = "choice_comment_likes"
    __table_args__ = (UniqueConstraint("comment_id", "user_id", name="uq_choice_comment_likes_comment_user"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey("choice_comments.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class ChoiceReply(Base):
    """댓글에 달리는 한 단계 답글. 좋아요는 지원하지 않는다."""

    __tablename__ = "choice_replies"
    __table_args__ = (
        CheckConstraint("length(trim(content)) BETWEEN 1 AND 1000", name="ck_choice_replies_content"),
        Index("ix_choice_replies_comment_id_id", "comment_id", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey("choice_comments.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    author: Mapped[User] = relationship()
