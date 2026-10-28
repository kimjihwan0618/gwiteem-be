"""기존 테스트 계정으로 댓글·답글을 보충한다. 기본은 미리보기, --apply로 저장."""
import argparse
import asyncio
import importlib
from datetime import datetime, timedelta

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.choice import ChoiceQuestion
from app.models.comment import ChoiceComment, ChoiceCommentLike, ChoiceReply
from app.models.user import User


REASONS = {
    "work": ["매일 반복되는 일이라 오래 유지할 수 있는지가 중요하더라고요", "요즘은 퇴근 후 내 시간을 지키는 쪽에 마음이 가요", "지금 커리어 단계에서는 새로운 경험이 더 필요해서요", "막상 해보니 제 성향에 맞는 환경이 제일 중요했어요"],
    "spending": ["당장 가격보다 얼마나 자주 쓸지를 먼저 보게 돼요", "예산을 정해 놓으니까 선택이 조금 쉬워지더라고요", "예전에 반대로 골랐다가 아쉬웠던 기억이 있어요", "결국 오래 만족할 수 있는 쪽으로 고르게 되네요"],
    "relationship": ["서로 부담 없이 오래 이어갈 수 있는 게 좋더라고요", "상대방 성향도 중요해서 정답 하나로 고르기는 어렵네요", "요즘 주변 사람들과 얘기해 보니 생각이 꽤 달랐어요", "저는 편하게 제 마음을 표현할 수 있는 쪽이 좋아요"],
    "daily": ["평소 생활 패턴에 잘 맞아서 꾸준히 할 수 있을 것 같아요", "하루가 바쁠수록 이런 작은 선택이 꽤 중요하더라고요", "주말에는 다른 쪽도 좋지만 평일 기준으로 골랐어요", "직접 해봤을 때 만족감이 더 오래 남았어요"],
}
OPENINGS = ['저는 ‘{option}’ 쪽이요.', '고민했는데 ‘{option}’에 한 표!', '지금 제 상황에서는 ‘{option}’ 쪽이 더 끌려요.', '둘 다 장점이 있지만 ‘{option}’ 쪽으로 골랐어요.', '예전과 달리 요즘은 ‘{option}’ 쪽이 좋아요.', '오늘 고른다면 ‘{option}’입니다.', '저도 ‘{option}’ 쪽을 선택했어요.', '끝까지 고민하다가 ‘{option}’ 쪽으로 정했어요.', '생각보다 어렵네요. 그래도 ‘{option}’!', '제 기준에는 ‘{option}’ 쪽이 조금 더 좋아요.', '경험상 ‘{option}’ 쪽이 잘 맞았어요.', '한 가지만 고르라면 ‘{option}’ 쪽이요.']
REPLIES = [
    "저도 비슷하게 생각했어요. 직접 해보니까 더 공감되네요.",
    "이런 관점은 생각 못 했네요. 선택한 이유 들으니 이해돼요.",
    "저는 반대쪽을 골랐는데, 상황에 따라 달라질 수 있겠네요.",
    "맞아요. 남들 기준보다 자기 생활에 맞는 게 중요한 것 같아요.",
    "저도 예전에는 달랐는데 요즘은 이쪽으로 마음이 기울어요.",
    "한번 경험해 보면 생각이 달라질 수도 있겠어요 ㅎㅎ",
    "결국 오래 유지할 수 있는지가 핵심인 것 같네요.",
    "주변에서도 의견이 갈리더라고요. 다른 생각 듣는 재미가 있어요.",
    "설명 듣고 다시 고민 중이에요. 둘 다 포기하기 어렵네요.",
    "저랑 비슷한 이유로 고르셨네요! 반가워요.",
    "공감해요. 무리하지 않는 쪽으로 선택하는 편이에요.",
    "사람마다 중요하게 보는 부분이 다른 게 흥미롭네요.",
]


async def seed(apply: bool) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    catalog = importlib.import_module("app.db.migrations.versions.fce3f83af5da_seed_local_test_users")
    emails = [email for email, _ in catalog.TEST_USERS]
    now = datetime.utcnow()
    added_comments = added_replies = added_likes = 0
    try:
        async with sessions() as db:
            await db.execute(text("SELECT pg_advisory_xact_lock(20261028, 87)"))
            users = list((await db.scalars(select(User).where(User.email.in_(emails), User.provider == "local").order_by(User.id))).all())
            if len(users) < 3:
                raise RuntimeError("기존 더미 계정이 3명 이상 필요합니다. 새 계정은 생성하지 않습니다.")
            questions = list((await db.scalars(select(ChoiceQuestion).order_by(ChoiceQuestion.id))).all())
            for question in questions:
                comments = list((await db.scalars(select(ChoiceComment).where(ChoiceComment.question_id == question.id).order_by(ChoiceComment.id))).all())
                target = 8 + question.id % 5
                options = [v for v in (question.option_a, question.option_b, question.option_c, question.option_d) if v]
                for index in range(len(comments), target):
                    option = options[(index + question.id) % len(options)]
                    content = OPENINGS[index % len(OPENINGS)].format(option=option) + "\n" + REASONS[question.category][(index + question.id) % 4]
                    start = max(question.published_at, now - timedelta(days=21))
                    age = max(0, int((now - start).total_seconds()))
                    created = start + timedelta(seconds=age * (index + 1) / (target + 1))
                    comment = ChoiceComment(question_id=question.id, user_id=users[(question.id + index * 3) % len(users)].id, content=content, created_at=created, updated_at=created)
                    db.add(comment)
                    await db.flush()
                    comments.append(comment)
                    added_comments += 1
                for comment in comments:
                    existing_replies = int(await db.scalar(select(func.count(ChoiceReply.id)).where(ChoiceReply.comment_id == comment.id)) or 0)
                    target_replies = 1 + comment.id % 3
                    candidates = [u for u in users if u.id != comment.user_id]
                    for index in range(existing_replies, target_replies):
                        created = min(now, comment.created_at + timedelta(minutes=13 + index * 47 + comment.id % 31))
                        db.add(ChoiceReply(comment_id=comment.id, user_id=candidates[(comment.id + index * 5) % len(candidates)].id,
                            content=REPLIES[(comment.id * 3 + index) % len(REPLIES)], created_at=created, updated_at=created))
                        added_replies += 1
                    liked_by = set((await db.scalars(select(ChoiceCommentLike.user_id).where(ChoiceCommentLike.comment_id == comment.id))).all())
                    for user in candidates[:comment.id % 7]:
                        if user.id not in liked_by:
                            db.add(ChoiceCommentLike(comment_id=comment.id, user_id=user.id))
                            added_likes += 1
            await db.flush()
            counts = list((await db.execute(select(ChoiceComment.question_id, func.count()).group_by(ChoiceComment.question_id))).all())
            reply_counts = list((await db.execute(select(ChoiceReply.comment_id, func.count()).group_by(ChoiceReply.comment_id))).all())
            total_comments = int(await db.scalar(select(func.count(ChoiceComment.id))) or 0)
            assert len(counts) == len(questions) and all(count >= 5 for _, count in counts)
            assert len(reply_counts) == total_comments and all(count >= 1 for _, count in reply_counts)
            print(f"질문 {len(questions)}개 / 기존 더미 유저 {len(users)}명")
            print(f"추가: 댓글 {added_comments}개, 답글 {added_replies}개, 댓글 좋아요 {added_likes}개")
            print(f"총 댓글 {total_comments}개 / 답글 {sum(count for _, count in reply_counts)}개")
            print(f"질문별 댓글 최소 {min(count for _, count in counts)}개 / 댓글별 답글 최소 {min(count for _, count in reply_counts)}개")
            if apply:
                await db.commit()
                print("저장 완료")
            else:
                await db.rollback()
                print("미리보기 완료. 저장하려면 --apply를 지정하세요.")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    asyncio.run(seed(parser.parse_args().apply))
