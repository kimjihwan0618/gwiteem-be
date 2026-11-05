"""카테고리 설정과 실제 질문 등록·조회·참여 흐름을 검증한다."""
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from app.core.choice_categories import CATEGORIES, ChoiceCategoryItem, CategoryCatalog
from app.models.choice import ChoiceQuestion, ChoiceReason
from app.tests.test_comments import api, auth


def payload() -> dict:
    return {"category": "daily", "title": " 주말에 딱 하루 쉰다면? ", "options": [" 집에서 쉬기 ", "밖에서 놀기"], "reasons": ["나에게 맞아서", "부담이 적어서"]}


@pytest.mark.asyncio
async def test_creation_and_vote(api) -> None:
    client, sessions = api
    categories = (await client.get("/api/v1/choices/categories")).json()["data"]
    assert categories == [item.model_dump() for item in CATEGORIES]
    assert (await client.post("/api/v1/choices/questions", json=payload())).status_code == 401
    response = await client.post("/api/v1/choices/questions", headers=auth(1), json=payload())
    assert response.status_code == 201, response.text
    question = response.json()["data"]
    assert question["title"] == "주말에 딱 하루 쉰다면?"
    assert question["option_a"] == "집에서 쉬기"
    assert question["author_name"] == "사용자1"
    assert question["category_label"] == "일상"
    assert question["is_daily"] is False
    assert len(question["reasons"]) == 2
    assert question["participant_count"] == 0
    question_id = question["id"]
    async with sessions() as db:
        stored = await db.get(ChoiceQuestion, question_id)
        assert stored.author_id == 1
    listed = (await client.get("/api/v1/choices/questions?sort=latest&category=daily")).json()["data"]["items"]
    assert listed[0]["id"] == question_id
    voted = await client.post(f"/api/v1/choices/questions/{question_id}/votes", headers=auth(2), json={"selected_option": "B", "reason_id": question["reasons"][0]["id"]})
    assert voted.status_code == 200
    assert voted.json()["data"]["question"]["result"]["total_count"] == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("changes", [
    {"category": "unknown"}, {"title": " "}, {"title": "가" * 201},
    {"options": ["하나"]}, {"options": ["A", "B", "C", "D", "E"]},
    {"options": ["같음", " 같음 "]}, {"options": [" ", "다름"]},
    {"options": ["가" * 101, "B"]}, {"reasons": []}, {"reasons": ["같음", "같음"]},
    {"reasons": ["가" * 121, "B"]}, {"author_id": 2}, {"is_daily": True},
])
async def test_invalid_creation_does_not_write(api, changes: dict) -> None:
    client, sessions = api
    response = await client.post("/api/v1/choices/questions", headers=auth(1), json={**payload(), **changes})
    assert response.status_code == 422
    async with sessions() as db:
        assert await db.scalar(select(func.count()).select_from(ChoiceQuestion)) == 3
        assert await db.scalar(select(func.count()).select_from(ChoiceReason)) == 0


@pytest.mark.asyncio
async def test_new_and_disabled_category_from_catalog(api) -> None:
    client, _ = api
    catalog = (*CATEGORIES, ChoiceCategoryItem(code="hobby", label="취미"))
    with patch("app.core.choice_categories.CATEGORIES", catalog), patch("app.routers.choice.CATEGORIES", catalog):
        result = await client.post("/api/v1/choices/questions", headers=auth(1), json={**payload(), "category": "hobby", "options": ["A", "B", "C", "D"]})
        assert result.status_code == 201
        assert result.json()["data"]["category_label"] == "취미"
        assert result.json()["data"]["option_d"] == "D"
        assert (await client.get("/api/v1/choices/questions?category=hobby")).status_code == 200
    catalog = tuple(item.model_copy(update={"enabled": False}) if item.code == "daily" else item for item in CATEGORIES)
    with patch("app.core.choice_categories.CATEGORIES", catalog):
        assert (await client.post("/api/v1/choices/questions", headers=auth(1), json=payload())).status_code == 422
        assert (await client.get("/api/v1/choices/questions?category=daily")).status_code == 200


def test_duplicate_category_code_is_rejected() -> None:
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        CategoryCatalog(categories=[CATEGORIES[0], CATEGORIES[0]])
