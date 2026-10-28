"""기존 더미 계정의 질문별 참여율을 70~100%로 보충한다."""
import argparse
import asyncio
import importlib
import math
import random
from collections import Counter
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.choice import ChoiceQuestion, ChoiceVote
from app.models.comment import ChoiceComment
from app.models.user import User


async def seed(apply: bool, seed_value: int) -> None:
    """질문별 고정 난수로 목표를 정하고 기존 투표를 변경하지 않고 추가한다."""
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    catalog = importlib.import_module(
        "app.db.migrations.versions.fce3f83af5da_seed_local_test_users"
    )
    emails = [email for email, _ in catalog.TEST_USERS]
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    added = 0
    distribution: Counter[int] = Counter()
    try:
        async with sessions() as db:
            await db.execute(text("SELECT pg_advisory_xact_lock(20261028, 88)"))
            users = list((await db.scalars(
                select(User.id).where(User.email.in_(emails), User.provider == "local")
                .order_by(User.id)
            )).all())
            if not users:
                raise RuntimeError("기존 더미 계정이 없습니다. 새 계정은 생성하지 않습니다.")
            minimum = math.ceil(len(users) * 0.7)
            questions = list((await db.scalars(
                select(ChoiceQuestion).options(selectinload(ChoiceQuestion.reasons))
                .order_by(ChoiceQuestion.id)
            )).all())
            for question in questions:
                if not question.reasons:
                    raise RuntimeError(f"질문 {question.id}에 선택 이유가 없습니다.")
                rng = random.Random(f"{seed_value}:{question.id}")
                target = rng.randint(minimum, len(users))
                existing = set((await db.scalars(
                    select(ChoiceVote.user_id).where(
                        ChoiceVote.question_id == question.id, ChoiceVote.user_id.in_(users)
                    )
                )).all())
                options = {
                    key: value for key, value in (
                        ("A", question.option_a), ("B", question.option_b),
                        ("C", question.option_c), ("D", question.option_d),
                    ) if value is not None
                }
                comments = list((await db.scalars(
                    select(ChoiceComment).where(
                        ChoiceComment.question_id == question.id,
                        ChoiceComment.user_id.in_(users),
                    ).order_by(ChoiceComment.id)
                )).all())
                comments_by_user = {comment.user_id: comment for comment in comments}
                candidates = [user_id for user_id in users if user_id not in existing]
                rng.shuffle(candidates)
                weights = [rng.uniform(0.4, 1.6) for _ in options]
                start = min(now, max(question.published_at, now - timedelta(days=21)))
                for user_id in candidates[:max(0, target - len(existing))]:
                    option = rng.choices(list(options), weights=weights, k=1)[0]
                    comment = comments_by_user.get(user_id)
                    # 앞서 만든 더미 댓글에서 선택을 명시했다면 그 선택과 일치시킨다.
                    if comment:
                        option = next((key for key, label in options.items()
                                       if f"‘{label}’" in comment.content), option)
                    end = max(start, min(now, comment.created_at)) if comment else now
                    created = start + (end - start) * rng.random()
                    db.add(ChoiceVote(
                        question_id=question.id, user_id=user_id, guest_session_id=None,
                        selected_option=option, reason_id=rng.choice(question.reasons).id,
                        created_at=created, updated_at=created,
                    ))
                    added += 1
                await db.flush()
                votes = list((await db.scalars(select(ChoiceVote).where(
                    ChoiceVote.question_id == question.id, ChoiceVote.user_id.in_(users)
                ))).all())
                if not minimum <= len(votes) <= len(users):
                    raise RuntimeError(f"질문 {question.id}의 참여율 범위를 확인해 주세요.")
                if len({vote.user_id for vote in votes}) != len(votes):
                    raise RuntimeError("질문별 중복 참여가 발견되었습니다.")
                reasons = {reason.id for reason in question.reasons}
                if any(vote.selected_option not in options or vote.reason_id not in reasons for vote in votes):
                    raise RuntimeError("질문에 속하지 않는 선택지 또는 이유가 있습니다.")
                distribution[len(votes)] += 1
            print(f"질문 {len(questions)}개 / 기존 더미 유저 {len(users)}명 / 추가 투표 {added}개")
            print(f"더미 유저 총 투표 {sum(count * questions for count, questions in distribution.items())}개")
            for count, question_count in sorted(distribution.items()):
                print(f"{count}명 참여 ({count / len(users):.0%}): 질문 {question_count}개")
            if apply:
                await db.commit()
                print("저장 완료. 기존 사용자·게스트 투표는 유지했습니다.")
            else:
                await db.rollback()
                print("미리보기 완료. --apply로 저장할 수 있습니다.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--seed", type=int, default=20261029)
    args = parser.parse_args()
    asyncio.run(seed(args.apply, args.seed))
