"""실제 HTTP/DB 경계에서 댓글 권한, 커서, 집계와 삭제를 검증한다."""
import importlib

import pytest
import pytest_asyncio
from alembic.migration import MigrationContext
from alembic.operations import Operations
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select, create_engine, inspect
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.core.deps import get_db
from app.core.security import create_access_token
from app.db.base import Base
from app.main import app
from app.models.choice import ChoiceQuestion
from app.models.comment import ChoiceCommentLike
from app.models.user import User


@pytest_asyncio.fixture
async def api():
    engine = create_async_engine("sqlite+aiosqlite://")
    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as db:
        db.add_all([User(id=i, nickname=f"사용자{i}", provider="local", provider_id=str(i)) for i in (1, 2)])
        db.add_all([ChoiceQuestion(id=i, category="daily", title=f"질문{i}", option_a="A", option_b="B", is_active=i != 3) for i in (1, 2, 3)])
        await db.commit()
    async def override_db():
        async with sessions() as db:
            yield db
    app.dependency_overrides[get_db] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, sessions
    app.dependency_overrides.clear()
    await engine.dispose()


def auth(user_id: int) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id)}"}


@pytest.mark.asyncio
async def test_comment_lifecycle_permissions_and_counts(api):
    client, sessions = api
    path = "/api/v1/choices/questions/1/comments"
    assert (await client.get(path)).json()["data"]["total_count"] == 0
    assert (await client.post(path, json={"content": "댓글"})).status_code == 401
    for content in ("   ", "\n\t", "가" * 1001):
        assert (await client.post(path, headers=auth(1), json={"content": content})).status_code == 422
    created = await client.post(path, headers=auth(1), json={"content": "  첫 댓글  "})
    assert created.status_code == 201
    cid = created.json()["data"]["id"]
    item_path = f"{path}/{cid}"
    rows = (await client.get(path, headers=auth(1))).json()["data"]
    assert rows["items"][0]["content"] == "첫 댓글"
    assert rows["items"][0]["is_mine"] is True
    assert (await client.get(path)).json()["data"]["items"][0]["is_mine"] is False
    for method in ("patch", "delete"):
        response = await client.request(method, item_path, headers=auth(2), **({"json": {"content": "수정"}} if method == "patch" else {}))
        assert response.status_code == 403
    assert (await client.patch(item_path, headers=auth(1), json={"content": "수정됨"})).status_code == 200
    assert (await client.put(f"{item_path}/like")).status_code == 401
    for _ in range(2):
        assert (await client.put(f"{item_path}/like", headers=auth(2))).status_code == 200
    row = (await client.get(path, headers=auth(2))).json()["data"]["items"][0]
    assert row["like_count"] == 1 and row["is_liked"] is True
    for _ in range(2):
        assert (await client.delete(f"{item_path}/like", headers=auth(2))).status_code == 200
    assert (await client.get(path)).json()["data"]["items"][0]["like_count"] == 0
    assert (await client.patch(f"/api/v1/choices/questions/2/comments/{cid}", headers=auth(1), json={"content": "다른 질문"})).status_code == 404
    assert (await client.get("/api/v1/choices/questions/3/comments")).status_code == 404
    assert (await client.post("/api/v1/choices/questions/999/comments", headers=auth(1), json={"content": "없음"})).status_code == 404
    detail = (await client.get("/api/v1/choices/questions/1")).json()["data"]
    assert detail["comment_count"] == 1
    questions = (await client.get("/api/v1/choices/questions")).json()["data"]["items"]
    assert next(q for q in questions if q["id"] == 1)["comment_count"] == 1
    await client.put(f"{item_path}/like", headers=auth(2))
    assert (await client.delete(item_path, headers=auth(1))).status_code == 200
    assert (await client.get(path)).json()["data"]["total_count"] == 0
    assert (await client.delete(item_path, headers=auth(1))).status_code == 404
    async with sessions() as db:
        assert await db.scalar(select(func.count(ChoiceCommentLike.id))) == 0


@pytest.mark.asyncio
async def test_comment_cursor_is_stable(api):
    client, _ = api
    path = "/api/v1/choices/questions/1/comments"
    for i in range(23):
        await client.post(path, headers=auth(1), json={"content": str(i)})
    first = (await client.get(path)).json()["data"]
    assert first["total_count"] == 23 and len(first["items"]) == 20
    await client.post(path, headers=auth(1), json={"content": "새 댓글"})
    second = (await client.get(path, params={"cursor": first["next_cursor"]})).json()["data"]
    assert len(second["items"]) == 3 and second["next_cursor"] is None
    assert not {i["id"] for i in first["items"]} & {i["id"] for i in second["items"]}
    assert (await client.get(path, params={"cursor": -1})).status_code == 422


def test_generated_migration_upgrade_and_downgrade():
    module = importlib.import_module("app.db.migrations.versions.1c159ec384dd_add_question_comments")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=[User.__table__, ChoiceQuestion.__table__])
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert "choice_comment_likes" in inspect(connection).get_table_names()
            module.downgrade()
            assert "choice_comments" not in inspect(connection).get_table_names()
            module.upgrade()
            assert "choice_comments" in inspect(connection).get_table_names()
    engine.dispose()


@pytest.mark.asyncio
async def test_replies_permissions_scope_and_cascade(api):
    from app.models.comment import ChoiceReply
    client, sessions = api
    path = "/api/v1/choices/questions/1/comments"
    created = await client.post(path, headers=auth(1), json={"content": "원댓글"})
    cid = created.json()["data"]["id"]
    reply_path = f"{path}/{cid}/replies"
    assert (await client.post(reply_path, json={"content": "답글"})).status_code == 401
    for content in ("  ", "가" * 1001):
        assert (await client.post(reply_path, headers=auth(2), json={"content": content})).status_code == 422
    response = await client.post(reply_path, headers=auth(2), json={"content": " 답글 내용 "})
    assert response.status_code == 201
    rid = response.json()["data"]["id"]
    item_path = f"{reply_path}/{rid}"
    item = (await client.get(path, headers=auth(2))).json()["data"]["items"][0]
    assert item["replies"][0]["content"] == "답글 내용"
    assert item["replies"][0]["is_mine"] is True
    assert "like_count" not in item["replies"][0]
    assert (await client.put(f"{item_path}/like", headers=auth(1))).status_code == 404
    assert (await client.patch(item_path, headers=auth(1), json={"content": "변경"})).status_code == 403
    assert (await client.delete(item_path, headers=auth(1))).status_code == 403
    assert (await client.patch(item_path, headers=auth(2), json={"content": "변경"})).status_code == 200
    wrong_path = f"/api/v1/choices/questions/2/comments/{cid}/replies/{rid}"
    assert (await client.delete(wrong_path, headers=auth(2))).status_code == 404
    assert (await client.delete(item_path, headers=auth(2))).status_code == 200
    await client.post(reply_path, headers=auth(2), json={"content": "연쇄 삭제 확인"})
    assert (await client.delete(f"{path}/{cid}", headers=auth(1))).status_code == 200
    async with sessions() as db:
        assert await db.scalar(select(func.count(ChoiceReply.id))) == 0


def test_reply_migration_upgrade_and_downgrade():
    from app.models.comment import ChoiceComment
    module = importlib.import_module("app.db.migrations.versions.87af8eca06fd_add_comment_replies")
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        Base.metadata.create_all(connection, tables=[User.__table__, ChoiceQuestion.__table__, ChoiceComment.__table__])
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
            assert "choice_replies" in inspect(connection).get_table_names()
            module.downgrade()
            assert "choice_replies" not in inspect(connection).get_table_names()
    engine.dispose()
