"""Regression checks for private keys, durable metadata and attributed review history."""

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from pathlib import Path
import importlib.util
from alembic.migration import MigrationContext
from alembic.operations import Operations

from app.config import Settings
from app.db.database import Base
from app.db.models import Attempt, CasePrompt, Concept, CriterionAssessment, Rubric, Session
from app.db.migrate_columns import ensure_schema_columns
from app.schemas import AssessmentReviewSubmit, CaseReviewSubmit, CasePromptOut, SessionCreate, TurnRequest
from app.routers import review
from app.routers import sessions as session_routes
from app.db.models import TurnIdempotency


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def test_nested_answer_keys_are_removed_without_mutating_private_source():
    diagram = {"correct_repair": "opt_disk", "options": [{"id": "disk", "correct": True,
        "nested": {"private_notes": "key", "label": "Disk"}}], "private": {"reference": "secret"}}
    case = CasePromptOut(id="case", stage="diagnostic", case_type="baseline", scenario_text="Explain.",
                         diagram_preset=diagram, cloze_preset={"blanks": [{"id": "b", "correct": "disk"}]})
    assert case.diagram_preset == {"options": [{"id": "disk", "nested": {"label": "Disk"}}]}
    assert case.cloze_preset == {"blanks": [{"id": "b"}]}
    assert diagram["correct_repair"] == "opt_disk"


def test_missing_security_settings_disable_review_and_randomize_local_signing(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("REVIEWER_API_KEY", raising=False)
    first, second = Settings(_env_file=None), Settings(_env_file=None)
    assert first.reviewer_api_key == ""
    assert len(first.secret_key) >= 32 and first.secret_key != second.secret_key
    monkeypatch.setattr(review, "get_settings", lambda: first)
    with pytest.raises(HTTPException) as error:
        review.verify_reviewer_auth("concept-check-reviewer-secret")
    assert error.value.status_code == 401


def test_production_refuses_missing_or_unsafe_signing_secret(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    for secret in ("", "change-me-in-production"):
        with pytest.raises(ValidationError, match="SECRET_KEY"):
            Settings(_env_file=None, environment="production", secret_key=secret)


def test_arbitrary_invalid_reviewer_keys_fail_closed(monkeypatch):
    settings = Settings(_env_file=None, reviewer_api_key="configured-test-key")
    monkeypatch.setattr(review, "get_settings", lambda: settings)
    with pytest.raises(HTTPException) as error:
        review.verify_reviewer_auth("invalid-\u2603")
    assert error.value.status_code == 401


def test_retired_published_reviewer_key_cannot_be_reenabled_by_stale_config(monkeypatch):
    settings = Settings(_env_file=None, reviewer_api_key="concept-check-reviewer-secret")
    monkeypatch.setattr(review, "get_settings", lambda: settings)
    with pytest.raises(HTTPException) as error:
        review.verify_reviewer_auth("concept-check-reviewer-secret")
    assert error.value.status_code == 401


def test_reviewer_must_resolve_inconsistent_legacy_rating_before_confirming(db):
    assessment, _, _ = make_assessment(db)
    assessment.rating = "demonstrated"
    assessment.met = False
    db.commit()
    with pytest.raises(HTTPException) as error:
        review.review_assessment(assessment.id, AssessmentReviewSubmit(status="reviewed"), True, db)
    assert error.value.status_code == 422


def test_legacy_rating_migration_preserves_uncertainty_and_existing_ratings():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE criterion_assessments (id TEXT PRIMARY KEY, met BOOLEAN)"))
        conn.execute(text("INSERT INTO criterion_assessments VALUES ('yes', 1), ('no', 0), ('unknown', NULL)"))
    ensure_schema_columns(engine)
    with engine.connect() as conn:
        ratings = dict(conn.execute(text("SELECT id, rating FROM criterion_assessments")).all())
    assert ratings == {"yes": "demonstrated", "no": "not_addressed", "unknown": "ambiguous_needs_clarification"}
    with engine.begin() as conn:
        conn.execute(text("UPDATE criterion_assessments SET rating='technical_failure' WHERE id='no'"))
    ensure_schema_columns(engine)
    with engine.connect() as conn:
        assert conn.execute(text("SELECT rating FROM criterion_assessments WHERE id='no'")).scalar() == "technical_failure"
    engine.dispose()


def make_assessment(db):
    concept = Concept(module="B", slug="test", title="Storage", description="Storage", enabled=True)
    db.add(concept)
    db.flush()
    case = CasePrompt(concept_id=concept.id, authored_id="baseline-one", stage="diagnostic", case_type="baseline", scenario_text="Original scenario")
    db.add(case)
    db.flush()
    db.add(Rubric(case_prompt_id=case.id, reference_answer="private reference", criteria=[{"criterion": "Writes disk"}]))
    session = Session(owner_id="owner", concept_id=concept.id, current_prompt_id=case.id)
    db.add(session)
    db.flush()
    attempt = Attempt(session_id=session.id, case_prompt_id=case.id, stage="diagnostic", answer_text="My answer")
    db.add(attempt)
    db.flush()
    assessment = CriterionAssessment(attempt_id=attempt.id, criterion="Writes disk", rating="not_addressed", met=False, evidence="Original proposal")
    db.add(assessment)
    db.commit()
    return assessment, case, session


def test_review_preserves_original_proposal_and_appends_attributed_history(db):
    assessment, _, _ = make_assessment(db)
    first = review.review_assessment(assessment.id, AssessmentReviewSubmit(status="corrected", rating="demonstrated", reviewer_name="Reviewer A", reviewer_notes="Explained clearly"), True, db)
    assert first["status"] == "ok"
    db.refresh(assessment)
    assert assessment.met is True and assessment.rating == "demonstrated"
    review.review_assessment(assessment.id, AssessmentReviewSubmit(status="corrected", met=False, reviewer_name="Reviewer B"), True, db)
    db.refresh(assessment)
    assert assessment.met is False and assessment.rating == "not_addressed"
    revisions = db.query(review.AssessmentReviewRevision).filter_by(assessment_id=assessment.id).order_by(review.AssessmentReviewRevision.created_at).all()
    assert len(revisions) == 2
    assert [r.reviewer_name for r in revisions] == ["Reviewer A", "Reviewer B"]
    assert all(r.proposal_snapshot["evidence"] == "Original proposal" for r in revisions)
    assert revisions[0].review_snapshot["rating"] == "demonstrated"
    assert revisions[1].previous_snapshot["rating"] == "demonstrated"


def test_review_rejects_inconsistent_explicit_rating():
    with pytest.raises(ValidationError):
        AssessmentReviewSubmit(status="corrected", met=False, rating="demonstrated", reviewer_name="Reviewer")


def test_turn_request_bounds_identifiers_and_includes_recovery_actions():
    for action in ("submit_practice", "finish_session", "retry_processing"):
        assert TurnRequest(client_turn_id="turn", expected_version=1, action=action).action == action
    for value in ("", "x" * 101):
        with pytest.raises(ValidationError):
            TurnRequest(client_turn_id=value, expected_version=1, action="continue")
    with pytest.raises(ValidationError):
        TurnRequest(client_turn_id="turn", expected_version=0, action="continue")


def test_models_store_processing_and_snapshot_metadata(db):
    _, case, session = make_assessment(db)
    session.baseline_prompt_ids = [case.id]
    session.processing_turn_id = "reserved-turn"
    session.processing_status = "failed"
    db.commit()
    db.expire_all()
    loaded = db.get(Session, session.id)
    assert loaded.baseline_prompt_ids == [case.id]
    assert loaded.processing_turn_id == "reserved-turn" and loaded.processing_status == "failed"
    columns = {c["name"] for c in inspect(db.bind).get_columns("attempts")}
    assert {"case_snapshot", "support_level", "processing_status"} <= columns


def test_case_review_creates_version_without_changing_historical_content(db):
    _, original, session = make_assessment(db)
    reviewed = review.review_case(original.id, CaseReviewSubmit(
        review_status="reviewed", reviewer_name="Case reviewer", scenario_text="Clarified scenario",
        reference_answer="Reviewed reference"), True, db)
    db.expire_all()
    old = db.get(CasePrompt, original.id)
    new = db.get(CasePrompt, reviewed["case_id"])
    assert old.scenario_text == "Original scenario" and old.rubric.reference_answer == "private reference"
    assert old.review_status == "unreviewed" and old.active is False
    assert new.version == 2 and new.active is True and new.review_status == "reviewed"
    assert new.scenario_text == "Clarified scenario" and new.rubric.reference_answer == "Reviewed reference"
    assert db.get(Session, session.id).current_prompt_id == old.id


def test_new_session_freezes_only_active_baseline_cases(db):
    _, baseline, old_session = make_assessment(db)
    db.add_all([
        CasePrompt(concept_id=baseline.concept_id, stage="diagnostic", case_type="baseline", scenario_text="Retired", active=False, sort_order=-1),
        CasePrompt(concept_id=baseline.concept_id, stage="diagnostic", case_type="practice", scenario_text="Practice", sort_order=-2),
    ])
    db.commit()
    result = session_routes.create_session(SessionCreate(concept_id=baseline.concept_id), "owner", db)
    stored = db.get(Session, result.id)
    assert stored.current_prompt_id == baseline.id
    assert stored.baseline_prompt_ids == [baseline.id]
    assert result.diagnostic_total == 1


def test_hydration_restores_only_own_pending_request(db):
    _, case, session = make_assessment(db)
    session.processing_turn_id = "own-turn-hash"
    session.processing_status = "failed"
    payload = {"client_turn_id": "original-turn", "expected_version": 1, "action": "submit_answer", "text": "Saved answer"}
    db.add(TurnIdempotency(client_turn_id="own-turn-hash", session_id=session.id,
                           request_payload=payload, state="failed"))
    db.commit()
    result = session_routes.get_session(session.id, "owner", db)
    assert result.pending_turn == payload and result.processing_status == "failed"
    record = db.get(TurnIdempotency, "own-turn-hash")
    record.session_id = "another-session"
    db.commit()
    assert session_routes.get_session(session.id, "owner", db).pending_turn is None


def test_alembic_upgrade_adds_foundation_without_inventing_legacy_ratings():
    versions = Path(__file__).parents[1] / "alembic" / "versions"
    migration_path = versions / "a14f20261018_data_foundation.py"
    assert migration_path.exists(), "A versioned migration must accompany startup upgrades"
    def load_migration(path, name):
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    initial = load_migration(versions / "e8a1d47b718c_initial_schema.py", "initial_migration")
    foundation = load_migration(migration_path, "foundation_migration")
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        with Operations.context(MigrationContext.configure(conn)):
            initial.upgrade()
            conn.execute(text("INSERT INTO attempts (id, session_id, case_prompt_id, stage, answer_text, created_at) VALUES ('attempt', 'session', 'case', 'investigate', 'Legacy revision', CURRENT_TIMESTAMP)"))
            conn.execute(text("INSERT INTO criterion_assessments (id, attempt_id, criterion, met, created_at) VALUES ('legacy', 'attempt', 'Durability', 0, CURRENT_TIMESTAMP)"))
            foundation.upgrade()
            assert conn.execute(text("SELECT support_level FROM attempts WHERE id='attempt'")).scalar() == "unknown"
            assert conn.execute(text("SELECT rating FROM criterion_assessments WHERE id='legacy'")).scalar() == "not_addressed"
            assert {"assessment_review_revisions", "case_review_revisions"} <= set(inspect(conn).get_table_names())
            assert {"processing_turn_id", "baseline_prompt_ids"} <= {c["name"] for c in inspect(conn).get_columns("sessions")}
    engine.dispose()
