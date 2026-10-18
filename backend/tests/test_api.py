"""Comprehensive automated verification suite for Concept Check.

Covers:
- Health check & provider unavailable reporting
- Concept catalogue & disabled concept handling
- Session creation & persistence in SQLite
- Private rubric / reference answer non-disclosure
- Idempotent turn submissions
- Version mismatch / concurrency control (409)
- Action validation per stage
- Cross-user access denial (403)
- Full lifecycle: Diagnostic -> Investigate -> Apply -> Review
- Reviewer verification routes
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.db.database import Base, get_db
from app.db.models import Concept, CasePrompt, Rubric
from app.seed_data import CONCEPTS, STORAGE_PERSISTENCE_CASES
from app.config import get_settings

TEST_REVIEWER_KEY = "explicit-test-reviewer-access-key"

# Test database setup (isolated in-memory SQLite with static pool for thread sharing)
from sqlalchemy.pool import StaticPool

TEST_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.create_all(bind=engine)

    # Seed concepts and cases
    db = TestingSessionLocal()
    concept_map = {}
    for c_data in CONCEPTS:
        c = Concept(**c_data)
        db.add(c)
        db.flush()
        concept_map[c.slug] = c.id

    sp_id = concept_map.get("storage-persistence")
    if sp_id:
        for case_data in STORAGE_PERSISTENCE_CASES:
            case_copy = dict(case_data)
            rubric_data = case_copy.pop("rubric", None)
            case = CasePrompt(concept_id=sp_id, **case_copy)
            db.add(case)
            db.flush()

            if rubric_data:
                rubric = Rubric(
                    case_prompt_id=case.id,
                    reference_answer=rubric_data["reference_answer"],
                    criteria=rubric_data["criteria"],
                )
                db.add(rubric)

    db.commit()
    db.close()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def client():
    # Fresh TestClient
    return TestClient(app)


# ── 1. Health Check ──────────────────────────────────────────────

def test_health_check(client):
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    # When keys are missing in test env, these must honestly report False
    assert isinstance(data["openai_available"], bool)
    assert isinstance(data["fish_audio_available"], bool)


# ── 2. Concept Catalogue ─────────────────────────────────────────

def test_get_concepts_catalogue(client):
    res = client.get("/v1/concepts")
    assert res.status_code == 200
    concepts = res.json()
    assert len(concepts) >= 1

    # Storage & persistence should be enabled
    sp = next((c for c in concepts if c["slug"] == "storage-persistence"), None)
    assert sp is not None
    assert sp["enabled"] is True
    assert sp["module"] == "B"

    # All seven authored banks are now available; review status stays on each case.
    assert {c["slug"] for c in concepts} >= {c["slug"] for c in CONCEPTS}


def test_create_session_disabled_concept(client):
    with TestingSessionLocal() as db:
        disabled = Concept(module="A", slug="not-ready-test", title="Not ready", description="Test-only unavailable content", enabled=False)
        db.add(disabled)
        db.commit()
        disabled_id = disabled.id

    # Attempting to start session on disabled concept should be rejected
    res = client.post("/v1/sessions", json={"concept_id": disabled_id})
    assert res.status_code == 400
    assert "not yet available" in res.json()["detail"]


# ── 3. Session Creation & Private Rubric Non-Disclosure ───────────

def test_create_session_and_non_disclosure(client):
    res = client.get("/v1/concepts")
    sp = next(c for c in res.json() if c["slug"] == "storage-persistence")

    res = client.post("/v1/sessions", json={"concept_id": sp["id"]})
    assert res.status_code == 201
    session_data = res.json()

    assert session_data["stage"] == "diagnostic"
    assert session_data["version"] == 1
    assert session_data["diagnostic_index"] == 0
    assert session_data["current_prompt"] is not None

    # CRITICAL: Reference answers and private rubrics MUST NOT be in the client payload!
    assert "rubric" not in session_data
    assert "reference_answer" not in session_data
    assert "criteria" not in session_data
    if session_data["current_prompt"]:
        assert "rubric" not in session_data["current_prompt"]
        assert "reference_answer" not in session_data["current_prompt"]


# ── 4. Cross-User Access Denial ──────────────────────────────────

def test_cross_user_denial(client):
    # User A creates a session
    client_a = TestClient(app)
    res_a = client_a.get("/v1/concepts")
    sp = next(c for c in res_a.json() if c["slug"] == "storage-persistence")
    create_res = client_a.post("/v1/sessions", json={"concept_id": sp["id"]})
    session_id = create_res.json()["id"]

    # User B (separate TestClient instance without User A's session cookie)
    client_b = TestClient(app)
    # B attempts to access A's session
    get_res = client_b.get(f"/v1/sessions/{session_id}")
    assert get_res.status_code == 403
    assert "Access denied" in get_res.json()["detail"]

    # B attempts to submit a turn on A's session
    turn_res = client_b.post(
        f"/v1/sessions/{session_id}/turns",
        json={
            "client_turn_id": "malicious-turn-1",
            "expected_version": 1,
            "action": "submit_answer",
            "text": "Intruder answer",
        },
    )
    assert turn_res.status_code == 403


# ── 5. Action Validation & Concurrency Version Control ───────────

def test_invalid_action_rejected(client):
    res = client.get("/v1/concepts")
    sp = next(c for c in res.json() if c["slug"] == "storage-persistence")
    create_res = client.post("/v1/sessions", json={"concept_id": sp["id"]})
    session_id = create_res.json()["id"]

    # In diagnostic stage, 'continue' or 'request_help' is NOT allowed
    bad_turn = client.post(
        f"/v1/sessions/{session_id}/turns",
        json={
            "client_turn_id": "turn-bad-action",
            "expected_version": 1,
            "action": "continue",
        },
    )
    assert bad_turn.status_code == 409
    assert "not allowed in stage 'diagnostic'" in bad_turn.json()["detail"]


def test_version_mismatch_rejected(client):
    res = client.get("/v1/concepts")
    sp = next(c for c in res.json() if c["slug"] == "storage-persistence")
    create_res = client.post("/v1/sessions", json={"concept_id": sp["id"]})
    session_id = create_res.json()["id"]

    # Expects version 1, but we pass expected_version=99
    mismatch_turn = client.post(
        f"/v1/sessions/{session_id}/turns",
        json={
            "client_turn_id": "turn-mismatch",
            "expected_version": 99,
            "action": "submit_answer",
            "text": "Some text",
        },
    )
    assert mismatch_turn.status_code == 409
    assert "Version mismatch" in mismatch_turn.json()["detail"]


# ── 6. Idempotent Turn Retry ─────────────────────────────────────

def test_idempotent_turn_retry(client):
    res = client.get("/v1/concepts")
    sp = next(c for c in res.json() if c["slug"] == "storage-persistence")
    create_res = client.post("/v1/sessions", json={"concept_id": sp["id"]})
    session_id = create_res.json()["id"]

    turn_id = "unique-idempotent-turn-123"
    turn_payload = {
        "client_turn_id": turn_id,
        "expected_version": 1,
        "action": "submit_answer",
        "text": "Data in RAM is volatile and is lost when the computer restarts.",
    }

    # First submission
    res1 = client.post(f"/v1/sessions/{session_id}/turns", json=turn_payload)
    assert res1.status_code == 200
    data1 = res1.json()

    # Second submission with the exact same client_turn_id
    res2 = client.post(f"/v1/sessions/{session_id}/turns", json=turn_payload)
    assert res2.status_code == 200
    data2 = res2.json()

    # Must return identical snapshot without duplicating attempts
    assert data1["version"] == data2["version"]
    assert data1["stage"] == data2["stage"]


# ── 7. Full Diagnostic -> Investigate -> Apply -> Review Lifecycle

def test_full_learning_lifecycle(client):
    res = client.get("/v1/concepts")
    sp = next(c for c in res.json() if c["slug"] == "storage-persistence")
    session = client.post("/v1/sessions", json={"concept_id": sp["id"]}).json()
    session_id = session["id"]

    # 1. Answer Diagnostic Case 1
    t1 = client.post(
        f"/v1/sessions/{session_id}/turns",
        json={
            "client_turn_id": "diag-1",
            "expected_version": 1,
            "action": "submit_answer",
            "text": "The note lives only in memory, so it is lost after restart because RAM is volatile.",
        },
    ).json()
    assert t1["stage"] == "diagnostic"
    assert t1["version"] == 2

    # 2. Answer Diagnostic Case 2
    t2 = client.post(
        f"/v1/sessions/{session_id}/turns",
        json={
            "client_turn_id": "diag-2",
            "expected_version": 2,
            "action": "submit_answer",
            "text": "Yes, because it was saved to a file on disk before crashing, so the file persists.",
        },
    ).json()
    assert t2["stage"] == "diagnostic"
    assert t2["version"] == 3

    # 3. Answer Diagnostic Case 3 (Completes baseline diagnostic)
    t3 = client.post(
        f"/v1/sessions/{session_id}/turns",
        json={
            "client_turn_id": "diag-3",
            "expected_version": 3,
            "action": "submit_answer",
            "text": "The in-memory variable messages are lost, but database messages survive on disk.",
        },
    ).json()
    # Should advance to either investigate or apply
    assert t3["stage"] in ["investigate", "apply"]
    assert t3["version"] == 4

    current_stage = t3["stage"]
    current_ver = 4

    # If in investigate, test investigation action
    if current_stage == "investigate":
        t_inv = client.post(
            f"/v1/sessions/{session_id}/turns",
            json={
                "client_turn_id": "inv-1",
                "expected_version": current_ver,
                "action": "continue",
            },
        ).json()
        assert t_inv["stage"] == "apply"
        current_stage = "apply"
        current_ver = t_inv["version"]

    # 4. Submit Apply Transfer Case
    assert current_stage == "apply"
    t_apply = client.post(
        f"/v1/sessions/{session_id}/turns",
        json={
            "client_turn_id": "apply-1",
            "expected_version": current_ver,
            "action": "submit_answer",
            "text": "The scores are lost because the crash occurred before the end of the match when DB saving happens.",
        },
    ).json()
    assert t_apply["stage"] in ["review", "completed"]

    # 5. Fetch Session Report
    rep_res = client.get(f"/v1/sessions/{session_id}/report")
    assert rep_res.status_code == 200
    report = rep_res.json()

    assert report["session_id"] == session_id
    assert report["concept_title"] == "Storage & persistence"
    assert report["outcome"] in ["gap_found", "no_gap", "inconclusive"]
    assert len(report["attempts"]) >= 3
    assert report["assessment_status"] in ["provisional", "reviewed"]


# ── 8. Reviewer Mechanism ────────────────────────────────────────

def test_reviewer_workflow(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "reviewer_api_key", TEST_REVIEWER_KEY)
    # Unauthorized access must fail closed with 401
    unauth_res = client.get("/v1/review/assessments")
    assert unauth_res.status_code == 401

    reviewer_headers = {"X-Reviewer-Key": TEST_REVIEWER_KEY}
    # Get provisional assessments with reviewer authorization
    res = client.get("/v1/review/assessments", headers=reviewer_headers)
    assert res.status_code == 200
    items = res.json()
    assert isinstance(items, list)

    if items:
        item = items[0]
        # Unauthorized post must fail closed with 401
        unauth_post = client.post(
            f"/v1/review/assessments/{item['id']}",
            json={"status": "reviewed", "met": True},
        )
        assert unauth_post.status_code == 401

        # Submit authorized human review
        review_res = client.post(
            f"/v1/review/assessments/{item['id']}",
            headers=reviewer_headers,
            json={
                "status": "reviewed",
                "met": True,
                "reviewer_notes": "Verified by human reviewer during test run.",
                "reviewer_name": "Test reviewer",
            },
        )
        assert review_res.status_code == 200
        assert review_res.json()["status"] == "ok"
