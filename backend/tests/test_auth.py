"""Tests for user authentication, registration, login, logout, and session migration."""

import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.auth import create_access_token
from app.config import get_settings
from app.db.models import Attachment, Session as LearningSession, Transcription, User


from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.db.database import Base, get_db

test_engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
Base.metadata.create_all(bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def client():
    with TestClient(app, base_url="https://testserver") as c:
        yield c




def test_auth_me_unauthenticated(client):
    res = client.get("/v1/auth/me")
    assert res.status_code == 200
    data = res.json()
    assert data["authenticated"] is False
    assert data["user"] is None


def test_user_signup_and_me(client):
    email = "testlearner@example.com"
    res = client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "securepassword123", "full_name": "Test Learner"},
    )
    assert res.status_code == 201
    data = res.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == email
    assert data["user"]["full_name"] == "Test Learner"

    token = data["access_token"]

    # Check /v1/auth/me with Bearer token
    me_res = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["authenticated"] is True
    assert me_data["user"]["email"] == email

    # Duplicate signup must be rejected
    dup_res = client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "anotherpassword", "full_name": "Another"},
    )
    assert dup_res.status_code == 400
    assert "already exists" in dup_res.json()["detail"]


def test_user_login_invalid_and_valid(client):
    email = "login_test@example.com"
    client.post(
        "/v1/auth/signup",
        json={"email": email, "password": "mypassword456", "full_name": "Login Tester"},
    )

    # Invalid password
    bad_res = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "wrongpassword"},
    )
    assert bad_res.status_code == 401

    # Nonexistent email
    no_user = client.post(
        "/v1/auth/login",
        json={"email": "nobody@example.com", "password": "somepassword"},
    )
    assert no_user.status_code == 401

    # Valid login
    good_res = client.post(
        "/v1/auth/login",
        json={"email": email, "password": "mypassword456"},
    )
    assert good_res.status_code == 200
    data = good_res.json()
    assert "access_token" in data
    assert data["user"]["email"] == email


def test_logout(client):
    res = client.post("/v1/auth/logout")
    assert res.status_code == 200
    assert res.json()["status"] == "logged_out"


def test_claim_anonymous_sessions_on_signup(client):
    from app.seed_data.seeding import seed_authored_data
    with TestSession() as db:
        seed_authored_data(db)

    # 1. Fetch available concepts
    concepts_res = client.get("/v1/concepts")
    assert concepts_res.status_code == 200
    concepts = concepts_res.json()
    assert len(concepts) > 0

    cid = concepts[0]["id"]

    # 2. Start anonymous session
    start_res = client.post("/v1/sessions", json={"concept_id": cid})
    assert start_res.status_code == 201
    session_id = start_res.json()["id"]


    # 3. Register user with the same client (which holds the cc_session cookie)
    user_res = client.post(
        "/v1/auth/signup",
        json={"email": "session_migrator@example.com", "password": "password123"},
    )
    assert user_res.status_code == 201
    user_id = user_res.json()["user"]["id"]

    # 4. Check DB directly: session owner_id should now equal user_id
    with TestSession() as db:
        sess = db.get(LearningSession, session_id)
        assert sess.owner_id == user_id


@pytest.fixture
def concept_id():
    from app.seed_data.seeding import seed_authored_data
    from app.db.models import Concept
    with TestSession() as db:
        seed_authored_data(db)
        return db.query(Concept).filter_by(enabled=True).first().id


def test_production_learning_routes_require_a_registered_user(client, concept_id, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    assert client.post("/v1/sessions", json={"concept_id": concept_id}).status_code == 401
    assert client.get("/v1/sessions").status_code == 401


def test_production_rejects_a_token_whose_user_no_longer_exists(client, concept_id, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    result = client.post("/v1/auth/signup", json={"email": "deleted-auth@example.com", "password": "password123"})
    token = result.json()["access_token"]
    assert client.post("/v1/sessions", json={"concept_id": concept_id}).status_code == 201
    with TestSession() as db:
        db.delete(db.get(User, result.json()["user"]["id"]))
        db.commit()
    assert client.get("/v1/sessions", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("authorization", ["Bearer invalid-token", "Basic invalid-token", "Bearer"])
def test_invalid_explicit_authorization_never_falls_back_to_another_identity(client, authorization):
    result = client.post("/v1/auth/signup", json={"email": f"bad-header-{authorization.split()[0].lower()}-{len(authorization)}@example.com", "password": "password123"})
    assert result.status_code == 201
    assert client.get("/v1/auth/me", headers={"Authorization": authorization}).status_code == 401
    assert client.get("/v1/sessions", headers={"Authorization": authorization}).status_code == 401


def test_expired_explicit_bearer_never_uses_valid_account_cookies(client):
    result = client.post("/v1/auth/signup", json={"email": "expired-header@example.com", "password": "password123"}).json()
    token = create_access_token(result["user"]["id"], result["user"]["email"], timedelta(seconds=-1))
    assert client.get("/v1/sessions", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("cookie_name", ["cc_auth_token", "cc_session"])
def test_profile_and_learning_routes_resolve_the_same_single_auth_cookie(client, concept_id, cookie_name):
    email = f"single-{cookie_name}@example.com"
    result = client.post("/v1/auth/signup", json={"email": email, "password": "password123"}).json()
    session = client.post("/v1/sessions", json={"concept_id": concept_id}).json()
    client.cookies.clear()
    client.cookies.set(cookie_name, result["access_token"])
    assert client.get("/v1/auth/me").json()["user"]["id"] == result["user"]["id"]
    assert session["id"] in [item["id"] for item in client.get("/v1/sessions").json()]


def test_profile_and_learning_routes_share_cookie_precedence_when_accounts_differ(client, concept_id):
    first = client.post("/v1/auth/signup", json={"email": "precedence-first@example.com", "password": "password123"}).json()
    first_session = client.post("/v1/sessions", json={"concept_id": concept_id}).json()
    second = client.post("/v1/auth/signup", json={"email": "precedence-second@example.com", "password": "password123"}).json()
    second_session = client.post("/v1/sessions", json={"concept_id": concept_id}).json()
    client.cookies.clear()
    client.cookies.set("cc_auth_token", second["access_token"])
    client.cookies.set("cc_session", first["access_token"])
    assert client.get("/v1/auth/me").json()["user"]["id"] == second["user"]["id"]
    ids = [item["id"] for item in client.get("/v1/sessions").json()]
    assert second_session["id"] in ids
    assert first_session["id"] not in ids


def test_claim_moves_attachment_and_transcription_ownership_with_the_session(client, concept_id):
    session = client.post("/v1/sessions", json={"concept_id": concept_id}).json()
    with TestSession() as db:
        owner = db.get(LearningSession, session["id"]).owner_id
        attachment = Attachment(session_id=session["id"], owner_id=owner, filename="fictional.png", content_type="image/png", storage_path="no-file-is-written")
        transcript = Transcription(session_id=session["id"], owner_id=owner, raw_transcript="Fictional speech", status="transcribed")
        foreign_session = LearningSession(owner_id="other-owner", concept_id=concept_id)
        db.add_all([attachment, transcript, foreign_session])
        db.flush()
        foreign = Attachment(session_id=foreign_session.id, owner_id="other-owner", filename="foreign.png", content_type="image/png", storage_path="no-file-is-written")
        db.add(foreign)
        db.commit()
        attachment_id, transcription_id, foreign_id = attachment.id, transcript.id, foreign.id
    result = client.post("/v1/auth/signup", json={"email": "claim-media@example.com", "password": "password123"}).json()
    with TestSession() as db:
        assert db.get(Attachment, attachment_id).owner_id == result["user"]["id"]
        assert db.get(Transcription, transcription_id).owner_id == result["user"]["id"]
        assert db.get(Attachment, foreign_id).owner_id == "other-owner"


def test_failed_claim_rolls_back_session_and_media_ownership(client, concept_id):
    account = client.post("/v1/auth/signup", json={"email": "claim-rollback@example.com", "password": "password123"})
    assert account.status_code == 201
    client.post("/v1/auth/logout")
    session = client.post("/v1/sessions", json={"concept_id": concept_id}).json()
    with TestSession() as db:
        owner = db.get(LearningSession, session["id"]).owner_id
        attachment = Attachment(session_id=session["id"], owner_id=owner, filename="fictional.png", content_type="image/png", storage_path="no-file-is-written")
        transcript = Transcription(session_id=session["id"], owner_id=owner, raw_transcript="Fictional speech", status="transcribed")
        db.add_all([attachment, transcript])
        db.commit()
        attachment_id, transcription_id = attachment.id, transcript.id

    def fail_media_update(connection, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("UPDATE TRANSCRIPTIONS"):
            raise RuntimeError("Disposable claim-write failure")

    event.listen(test_engine, "before_cursor_execute", fail_media_update)
    try:
        with pytest.raises(RuntimeError, match="Disposable claim-write failure"):
            client.post("/v1/auth/login", json={"email": "claim-rollback@example.com", "password": "password123"})
    finally:
        event.remove(test_engine, "before_cursor_execute", fail_media_update)
    with TestSession() as db:
        assert db.get(LearningSession, session["id"]).owner_id == owner
        assert db.get(Attachment, attachment_id).owner_id == owner
        assert db.get(Transcription, transcription_id).owner_id == owner


def test_production_login_and_logout_cookies_use_the_same_secure_scope(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "environment", "production")
    signup = client.post("/v1/auth/signup", json={"email": "secure-cookie@example.com", "password": "password123"})
    assert signup.status_code == 201
    logout = client.post("/v1/auth/logout")
    for response in (signup, logout):
        cookies = response.headers.get_list("set-cookie")
        assert len(cookies) == 2
        assert all("Secure" in cookie and "HttpOnly" in cookie and "Path=/" in cookie and "SameSite=lax" in cookie for cookie in cookies)
    assert client.get("/v1/auth/me").json()["authenticated"] is False

