"""
모든 모델을 여기서 import해두면 Alembic의 `target_metadata = Base.metadata`가
app.models 패키지 import 한 번으로 전체 테이블을 인식할 수 있다.
(개별 모델 파일이 새로 추가되면 이 파일에도 import를 추가해야 한다.)
"""
from app.models.choice import ChoiceLike, ChoiceQuestion, ChoiceReason, ChoiceVote  # noqa: F401
from app.models.user import User  # noqa: F401

__all__ = [
    "User",
    "ChoiceQuestion",
    "ChoiceReason",
    "ChoiceVote",
    "ChoiceLike",
]
