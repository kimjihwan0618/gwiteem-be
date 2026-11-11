"""작성 질문의 인증, 작성자 분리, 검색과 페이지 경계를 검증한다."""
import pytest
from app.models.choice import ChoiceQuestion
from app.tests.test_question_pagination import populate, TestApi
from app.tests.test_comments import api, auth  # noqa: F401

@pytest.mark.asyncio
async def test_my_created_questions(api: TestApi) -> None:
    client, sessions = api
    await populate(sessions)
    async with sessions() as db:
        db.add_all([
            ChoiceQuestion(author_id=2, category="daily", title="다른 작성자", option_a="A", option_b="B"),
            ChoiceQuestion(author_id=1, category="daily", title="숨긴 질문", option_a="A", option_b="B", is_active=False),
        ])
        await db.commit()
    path = "/api/v1/choices/me/questions"
    assert (await client.get(path)).status_code == 401
    for sort in ("latest", "popular", "liked"):
        params = {"sort": sort}
        ids = []
        while True:
            response = await client.get(path, params=params, headers=auth(1))
            assert response.status_code == 200, response.text
            page = response.json()["data"]
            ids.extend(item["id"] for item in page["items"])
            if not page["next_cursor"]:
                break
            assert len(page["items"]) == 15
            params["cursor"] = page["next_cursor"]
        assert len(ids) == len(set(ids)) == 35
        assert set(ids) == set(range(10, 45))
    other = (await client.get(path, headers=auth(2))).json()["data"]["items"]
    assert [q["title"] for q in other] == ["다른 작성자"]
    found = (await client.get(path, headers=auth(1), params={"q": "마지막검색전용"})).json()["data"]
    assert [q["id"] for q in found["items"]] == [10]
    assert (await client.get(path, headers=auth(1), params={"q": "마지막검색전용", "category": "work"})).json()["data"]["items"] == []
    cursor = (await client.get(path, headers=auth(1))).json()["data"]["next_cursor"]
    assert (await client.get(path, headers=auth(2), params={"cursor": cursor})).status_code == 400
    assert (await client.get("/api/v1/choices/questions", headers=auth(1), params={"cursor": cursor})).status_code == 400
