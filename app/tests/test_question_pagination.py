"""질문 목록의 DB 검색, 페이지 경계, 정렬 및 사용자별 조회를 검증한다."""

from datetime import datetime

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from app.models.choice import ChoiceLike, ChoiceQuestion, ChoiceReason, ChoiceVote
from app.tests.test_comments import api, auth  # noqa: F401

TestApi = tuple[AsyncClient, async_sessionmaker[AsyncSession]]


async def populate(sessions: async_sessionmaker[AsyncSession]) -> None:
    """같은 게시 시각과 서로 다른 참여 수를 갖는 질문을 생성한다."""
    async with sessions() as db:
        for i in range(10, 45):
            db.add(ChoiceQuestion(
                id=i, author_id=1, category="work" if i % 2 else "daily",
                title="마지막검색전용" if i == 10 else "100%_완료" if i == 11 else f"페이지 질문 {i}",
                option_a="A", option_b="B", published_at=datetime(2026, 10, 1),
            ))
        await db.flush()
        for i in range(10, 45):
            reason = ChoiceReason(question_id=i, label="이유", sort_order=1)
            db.add(reason)
            await db.flush()
            db.add(ChoiceVote(question_id=i, user_id=1, selected_option="A", reason_id=reason.id))
            if i % 3 == 0:
                db.add(ChoiceVote(question_id=i, user_id=2, selected_option="B", reason_id=reason.id))
            if i % 2 == 0:
                db.add(ChoiceLike(question_id=i, user_id=1))
        await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("sort", ["latest", "popular", "liked"])
async def test_question_pages_and_server_search(api: TestApi, sort: str) -> None:
    client, sessions = api
    await populate(sessions)
    path = "/api/v1/choices/questions"
    params = {"sort": sort}
    seen = []
    while True:
        response = await client.get(path, params=params)
        assert response.status_code == 200, response.text
        page = response.json()["data"]
        assert 0 < len(page["items"]) <= 15
        seen.extend(item["id"] for item in page["items"])
        if page["next_cursor"] is None:
            break
        assert len(page["items"]) == 15
        params["cursor"] = page["next_cursor"]
    assert len(seen) == len(set(seen)) == 37
    assert 3 not in seen
    metric_ids = [i for i in seen if i >= 10]
    if sort == "popular":
        assert metric_ids == sorted(range(10, 45), key=lambda i: (i % 3 == 0, i), reverse=True)
    elif sort == "liked":
        assert metric_ids == sorted(range(10, 45), key=lambda i: (i % 2 == 0, i), reverse=True)
    else:
        assert metric_ids == list(range(44, 9, -1))
    search = (await client.get(path, params={"q": "  마지막검색전용  "})).json()["data"]
    assert [item["id"] for item in search["items"]] == [10]
    assert search["next_cursor"] is None
    for literal in ("%", "_"):
        page = (await client.get(path, params={"q": literal})).json()["data"]
        assert [item["id"] for item in page["items"]] == [11]
    page = (await client.get(path, params=[("category", "work"), ("category", "daily"), ("q", "페이지")])).json()["data"]
    assert len(page["items"]) == 15
    page = (await client.get(path, params={"category": "work", "q": "마지막검색전용"})).json()["data"]
    assert page["items"] == []


@pytest.mark.asyncio
async def test_cursor_validation_and_new_question(api: TestApi) -> None:
    client, sessions = api
    await populate(sessions)
    path = "/api/v1/choices/questions"
    first = (await client.get(path, params={"sort": "latest"})).json()["data"]
    async with sessions() as db:
        db.add(ChoiceQuestion(category="daily", title="새 질문", option_a="A", option_b="B",
                              published_at=datetime(2099, 1, 1)))
        await db.commit()
    second = (await client.get(path, params={"sort": "latest", "cursor": first["next_cursor"]})).json()["data"]
    assert not {item["id"] for item in first["items"]} & {item["id"] for item in second["items"]}
    assert all(item["title"] != "새 질문" for item in second["items"])
    assert (await client.get(path, params={"cursor": "invalid"})).status_code == 400
    assert (await client.get(path, params={"cursor": first["next_cursor"], "q": "다른 검색"})).status_code == 400
    for params in ({"limit": 16}, {"limit": 0}, {"category": "unknown"}, {"q": "가" * 201}):
        assert (await client.get(path, params=params)).status_code == 422


@pytest.mark.asyncio
@pytest.mark.parametrize("suffix,expected", [("", 35), ("/likes", 18)])
async def test_personal_pages_and_search(api: TestApi, suffix: str, expected: int) -> None:
    client, sessions = api
    await populate(sessions)
    path = f"/api/v1/choices/me{suffix}"
    assert (await client.get(path)).status_code == 401
    params = {"sort": "latest"}
    ids = []
    while True:
        response = await client.get(path, params=params, headers=auth(1))
        assert response.status_code == 200, response.text
        page = response.json()["data"]
        assert len(page["items"]) <= 15
        ids.extend(item["question"]["id"] for item in page["items"])
        if not page["next_cursor"]:
            break
        params["cursor"] = page["next_cursor"]
    assert len(set(ids)) == len(ids) == expected
    search = (await client.get(path, params={"q": "마지막검색전용"}, headers=auth(1))).json()["data"]
    assert [item["question"]["id"] for item in search["items"]] == [10]
    # 다른 사용자의 좋아요 및 투표 기록은 포함하지 않는다.
    own = (await client.get(path, params={"q": "마지막검색전용"}, headers=auth(2))).json()["data"]
    assert own["items"] == []
