"""
모든 모델을 여기서 import해두면 Alembic의 `target_metadata = Base.metadata`가
app.models 패키지 import 한 번으로 전체 테이블을 인식할 수 있다.
(개별 모델 파일이 새로 추가되면 이 파일에도 import를 추가해야 한다.)
"""
from app.models.briefing import DailyBriefing, SharedBriefing, UserBriefing  # noqa: F401
from app.models.commute import CommuteFavorite, CommuteQuery, CommuteRoute  # noqa: F401
from app.models.news import (  # noqa: F401
    InterestEmbedding,
    IssueCluster,
    NewsEmbedding,
    RawArticle,
)
from app.models.schedule import Schedule  # noqa: F401
from app.models.stock import Stock  # noqa: F401
from app.models.user import GuestInterest, User, UserInterest  # noqa: F401

__all__ = [
    "User",
    "UserInterest",
    "GuestInterest",
    "Stock",
    "RawArticle",
    "IssueCluster",
    "NewsEmbedding",
    "InterestEmbedding",
    "DailyBriefing",
    "UserBriefing",
    "SharedBriefing",
    "CommuteRoute",
    "CommuteQuery",
    "CommuteFavorite",
    "Schedule",
]
