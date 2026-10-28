"""생성 계정의 이름과 참여 데이터를 자연스러운 분포로 갱신한다."""

import argparse
import asyncio
import importlib
import json
import random
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.base import Base
from app.models.choice import ChoiceLike, ChoiceQuestion, ChoiceVote
from app.models.comment import ChoiceComment, ChoiceCommentLike, ChoiceReply
from app.models.user import User
from scripts.seed_choice_discussions import OPENINGS, REASONS, REPLIES


NAMES = (
    "김민준", "이서연", "박지훈", "최유진", "정현우", "강수빈", "조민재",
    "윤하늘", "장도윤", "임지아", "한승우", "오채원", "서준호", "신예린",
    "권태윤", "송다은", "황재현", "안소희", "배정우", "문예진",
)
EMAILS = tuple(f"demo{i:02d}@example.test" for i in range(1, 21))
LEGACY_REPLY = "공감해요. 각자의 생활과 우선순위에 따라 달라질 것 같아요."


def generated_comment(content: str, question: ChoiceQuestion) -> bool:
    """생성 계정이 작성한 기존 템플릿 댓글만 갱신 대상으로 인식한다."""
    legacy = {
        f"{question.title} 제 상황에 맞는 선택과 오래 유지할 수 있는지가 중요하다고 생각해요. ({i})"
        for i in range(1, 6)
    }
    options = (question.option_a, question.option_b, question.option_c, question.option_d)
    candidates = {
        opening.format(option=option) + "\n" + reason
        for option in options if option
        for opening in OPENINGS for reason in REASONS[question.category]
    }
    return content in legacy or content in candidates


def between(rng: random.Random, start: datetime, end: datetime) -> datetime:
    """부모 항목보다 이르지 않은 참여 시각을 만든다."""
    return start + max(end - start, timedelta()) * rng.random()


async def refresh_activity(db: AsyncSession, seed: int = 20261028) -> dict[str, int]:
    """명확히 식별된 생성 데이터만 교체하고 다른 사용자의 활동은 보존한다."""
    users = list((await db.scalars(select(User).where(User.email.in_(EMAILS)))).all())
    by_email = {user.email: user for user in users}
    if len(users) != 20 or any(user.provider != "local" or user.provider_id != user.email for user in users):
        raise RuntimeError("갱신할 생성 계정 20명의 식별자가 일치하지 않습니다.")
    users = [by_email[email] for email in EMAILS]
    user_ids = {user.id for user in users}
    conflicts = await db.scalar(select(func.count()).select_from(User).where(
        User.nickname.in_(NAMES), User.id.not_in(user_ids)
    ))
    if conflicts:
        raise RuntimeError("선택한 이름이 기존 사용자와 겹칩니다. 이름 목록을 조정하세요.")
    now = datetime.utcnow()
    for user in users:
        user.nickname = f"rename-{uuid4().hex}"
    await db.flush()
    for i, user in enumerate(users):
        user.nickname = NAMES[i]
        user.updated_at = now
        user.created_at = min(user.created_at, now - timedelta(days=45 + i * 3))
    await db.flush()

    catalog = importlib.import_module("app.db.migrations.versions.6108ff5d4fe3_seed_choice_question_catalog")
    titles = {title for entries in catalog.QUESTION_CATALOG.values() for title, _, _ in entries}
    questions = list((await db.scalars(select(ChoiceQuestion).options(
        selectinload(ChoiceQuestion.reasons)
    ).where(ChoiceQuestion.title.in_(titles), ChoiceQuestion.author_id.in_(user_ids))
        .order_by(ChoiceQuestion.id))).all())
    total_questions = int(await db.scalar(select(func.count()).select_from(ChoiceQuestion)) or 0)
    if not 30 <= total_questions <= 35 or len(questions) != len(titles):
        raise RuntimeError("질문 수 또는 생성 질문 식별자가 예상과 다릅니다. 기존 질문은 삭제하지 않습니다.")
    distributions: list[dict[str, int]] = []
    protected_reply_count = 0
    for question in questions:
        rng = random.Random(f"{seed}:{question.id}")
        comments = list((await db.scalars(select(ChoiceComment).where(
            ChoiceComment.question_id == question.id
        ))).all())
        managed = {c.id: c for c in comments if c.user_id in user_ids and generated_comment(c.content, question)}
        replies = list((await db.scalars(select(ChoiceReply).where(
            ChoiceReply.comment_id.in_([c.id for c in comments])
        ))).all())
        generated_replies = [r for r in replies if r.comment_id in managed
                             and r.user_id in user_ids and r.content in [*REPLIES, LEGACY_REPLY]]
        generated_reply_ids = {r.id for r in generated_replies}
        protected_replies = [r for r in replies if r.id not in generated_reply_ids]
        protected_reply_count += len(protected_replies)
        protected_parents = {r.comment_id for r in protected_replies}
        protected_parents.update((await db.scalars(select(ChoiceCommentLike.comment_id).where(
            ChoiceCommentLike.comment_id.in_(managed), ChoiceCommentLike.user_id.not_in(user_ids)
        ))).all())
        retained = [c for c in managed.values() if c.id in protected_parents]

        await db.execute(delete(ChoiceReply).where(ChoiceReply.id.in_(generated_reply_ids)))
        await db.execute(delete(ChoiceCommentLike).where(
            ChoiceCommentLike.comment_id.in_(managed), ChoiceCommentLike.user_id.in_(user_ids)
        ))
        await db.execute(delete(ChoiceComment).where(
            ChoiceComment.id.in_(set(managed) - protected_parents)
        ))
        for model in (ChoiceVote, ChoiceLike):
            await db.execute(delete(model).where(
                model.question_id == question.id, model.user_id.in_(user_ids)
            ))

        preserved_times = [c.created_at for c in comments if c.id not in managed or c.id in protected_parents]
        for model in (ChoiceVote, ChoiceLike):
            preserved_times.extend((await db.scalars(select(model.created_at).where(
                model.question_id == question.id, model.user_id.not_in(user_ids)
            ))).all())
        created = now - timedelta(days=rng.uniform(1, 28))
        if preserved_times:
            created = min(created, min(preserved_times) - timedelta(hours=1))
        question.created_at = question.published_at = created
        question.author_id = rng.choice(users).id
        options = {key: label for key, label in (
            ("A", question.option_a), ("B", question.option_b),
            ("C", question.option_c), ("D", question.option_d),
        ) if label is not None}
        if not question.reasons:
            raise RuntimeError("선택 이유가 없는 질문은 갱신할 수 없습니다.")
        voters = rng.sample(users, rng.randint(5, 20))
        for comment in retained:
            if comment.user_id not in {user.id for user in voters}:
                voters.append(next(user for user in users if user.id == comment.user_id))
        votes: dict[int, ChoiceVote] = {}
        weights = [rng.uniform(0.2, 2.5) for _ in options]
        for user in voters:
            voted_at = between(rng, created, now)
            previous = [c.created_at for c in retained if c.user_id == user.id]
            if previous:
                voted_at = min(voted_at, min(previous))
            vote = ChoiceVote(question_id=question.id, user_id=user.id,
                              selected_option=rng.choices(list(options), weights=weights)[0],
                              reason_id=rng.choice(question.reasons).id,
                              created_at=voted_at, updated_at=voted_at)
            votes[user.id] = vote
            db.add(vote)
        for user in rng.sample(users, rng.randint(0, 19)):
            db.add(ChoiceLike(question_id=question.id, user_id=user.id,
                              created_at=between(rng, created, now)))

        target = rng.choices([rng.randint(0, 2), rng.randint(3, 8), rng.randint(9, 16)], weights=[2, 5, 3])[0]
        target = min(len(voters), max(len(retained), target))
        active_comments = list(retained)
        candidates = [u for u in voters if u.id not in {c.user_id for c in retained}]
        for user in rng.sample(candidates, max(0, target - len(retained))):
            commented_at = between(rng, votes[user.id].created_at, now)
            comment = ChoiceComment(question_id=question.id, user_id=user.id, content="작성 중",
                                    created_at=commented_at, updated_at=commented_at)
            db.add(comment)
            active_comments.append(comment)
        used_contents: set[str] = set()
        for comment in active_comments:
            label = options[votes[comment.user_id].selected_option]
            contents = [opening.format(option=label) + "\n" + reason
                        for opening in OPENINGS for reason in REASONS[question.category]]
            comment.content = rng.choice([content for content in contents if content not in used_contents])
            used_contents.add(comment.content)
            # 보호된 답글의 부모 댓글은 ID와 작성 시각을 유지한다.
            comment.updated_at = comment.created_at
            await db.flush()
            responders = [user for user in users if user.id != comment.user_id]
            reply_count = rng.choices([0, 1, 2, 3, 4], weights=[5, 4, 2, 1, 1])[0]
            for content in rng.sample(REPLIES, reply_count):
                replied_at = between(rng, comment.created_at, now)
                db.add(ChoiceReply(comment_id=comment.id, user_id=rng.choice(responders).id,
                                   content=content, created_at=replied_at, updated_at=replied_at))
            like_count = min(len(responders), int(rng.triangular(0, 16, 1)))
            for user in rng.sample(responders, like_count):
                db.add(ChoiceCommentLike(comment_id=comment.id, user_id=user.id))
        await db.flush()
        distributions.append({
            "question_id": question.id,
            "comments": int(await db.scalar(select(func.count()).select_from(ChoiceComment).where(ChoiceComment.question_id == question.id)) or 0),
            "replies": int(await db.scalar(select(func.count()).select_from(ChoiceReply).join(ChoiceComment, ChoiceReply.comment_id == ChoiceComment.id).where(ChoiceComment.question_id == question.id)) or 0),
            "likes": int(await db.scalar(select(func.count()).select_from(ChoiceLike).where(ChoiceLike.question_id == question.id)) or 0),
        })
    await db.flush()
    counts = {table.name: int(await db.scalar(select(func.count()).select_from(table)) or 0)
              for table in Base.metadata.sorted_tables}
    print(json.dumps(counts, ensure_ascii=False))
    for key in ("comments", "replies", "likes"):
        values = [item[key] for item in distributions]
        print(f"질문별 {key}: 최소 {min(values)}, 최대 {max(values)}, 서로 다른 개수 {len(set(values))}종")
    print(f"기존 사용자 작성 답글 보존: {protected_reply_count}개")
    return counts


async def backup_database(db: AsyncSession) -> Path:
    """적용 전에 현재 테이블 데이터를 Git에서 제외된 로컬 파일로 저장한다."""
    directory = Path(__file__).resolve().parents[1] / ".database-backups"
    directory.mkdir(exist_ok=True)
    path = directory / f"activity-before-{datetime.utcnow():%Y%m%d-%H%M%S-%f}.json"
    snapshot = {}
    for table in Base.metadata.sorted_tables:
        snapshot[table.name] = [dict(row) for row in (await db.execute(select(table))).mappings()]
    path.write_text(json.dumps(snapshot, ensure_ascii=False, default=str, indent=2), encoding="utf-8")
    return path


async def main(apply: bool, seed: int) -> None:
    """미리보기는 롤백하고 실제 적용은 백업 후 단일 트랜잭션으로 저장한다."""
    from scripts.bootstrap_database import prepare_schema

    engine = create_async_engine(settings.DATABASE_URL, connect_args={"timeout": 8}, echo=False)
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL statement_timeout = '60s'"))
            await connection.execute(text("SELECT pg_advisory_xact_lock(20261028, 89)"))
            await connection.run_sync(prepare_schema, False)
            async with AsyncSession(bind=connection, expire_on_commit=False) as db:
                if apply:
                    print(f"백업: {await backup_database(db)}")
                await refresh_activity(db, seed)
                if apply:
                    await db.commit()
            if not apply:
                await connection.rollback()
        print("저장 완료" if apply else "미리보기 완료. --apply로 저장하세요.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--seed", type=int, default=20261028)
    args = parser.parse_args()
    try:
        asyncio.run(main(args.apply, args.seed))
    except Exception as exc:
        print(f"실행 실패: {type(exc).__name__}. 트랜잭션은 롤백되었습니다.")
        raise SystemExit(1) from None
