"""Tests for user authentication, registration, login, logout, and session migration."""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.db.database import get_db, SessionLocal
from app.db.models import Session as LearningSession, User


from sqlalchemy import create_engine
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
    with TestClient(app) as c:
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

