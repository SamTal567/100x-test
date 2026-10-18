"""Authored-content contracts and history-safe seeding; disposable SQLite only."""

from copy import deepcopy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.database import Base
from app.db.models import Attempt, CasePrompt, CaseReviewRevision, Concept, Rubric, Session
from app.seed_data import CASE_BANKS, CONCEPTS, STORAGE_PERSISTENCE_CASES
from app.seed_data.seeding import seed_authored_data
from app.resources import render_resource


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as session:
        yield session
    engine.dispose()


def skills(cases):
    return {item["skill_id"] for case in cases for item in case["rubric"]["criteria"]}


def test_enabled_banks_have_complete_matched_progression_and_private_authoring_notes():
    assert len(CASE_BANKS) == 7
    assert {c["slug"] for c in CONCEPTS if c["enabled"]} == set(CASE_BANKS)
    identities = []
    for slug, cases in CASE_BANKS.items():
        baseline = [c for c in cases if c["case_type"] == "baseline"]
        practice = [c for c in cases if c["case_type"] == "guided_practice"]
        transfer = [c for c in cases if c["case_type"] == "transfer"]
        confirmation = [c for c in cases if c["case_type"] == "confirmation"]
        assert len(baseline) >= 2, slug
        assert len(practice) >= 2 and any(c.get("diagram_preset") for c in practice), slug
        assert any(c.get("cloze_preset") for c in practice), slug
        assert len(transfer) >= 2 and confirmation, slug
        assert skills(transfer) <= skills(baseline), slug
        assert skills(baseline) <= skills(transfer), slug
        assert skills(confirmation) <= skills(baseline), slug
        for case in cases:
            identities.append(case["authored_id"])
            assert case["source"] == "ai-authored" and case["review_status"] == "unreviewed"
            assert case["assumptions"] and case["rubric"]["reference_answer"]
            for item in case["rubric"]["criteria"]:
                for key in ("acceptable_alternatives", "common_misconceptions", "follow_up_probes"):
                    assert item[key], (slug, key)
    assert len(identities) == len(set(identities))


def test_objective_presets_have_valid_private_keys_and_stable_repair_edges():
    for cases in CASE_BANKS.values():
        for case in cases:
            diagram = case.get("diagram_preset")
            if diagram:
                nodes = {n["id"] for n in diagram["nodes"]}
                for edge in diagram["edges"]:
                    assert edge["from"] in nodes and edge["to"] in nodes
                if diagram.get("repair_options"):
                    assert diagram["correct_repair"] in {o["id"] for o in diagram["repair_options"]}
                    assert diagram["repair_edge_id"] in {e["id"] for e in diagram["edges"]}
                    assert all(o["target_node"] in nodes for o in diagram["repair_options"])
            for preset in (diagram, case.get("cloze_preset")):
                if preset:
                    for blank in preset.get("blanks", []):
                        assert blank["id"] and blank["correct"] in blank["options"]


def test_storage_retains_required_formats_and_removes_unassessed_authentication_and_absolute_guarantee():
    assert len(STORAGE_PERSISTENCE_CASES) >= 12
    assert sum(bool(c.get("diagram_preset")) for c in STORAGE_PERSISTENCE_CASES) >= 7
    assert sum(bool(c.get("cloze_preset")) for c in STORAGE_PERSISTENCE_CASES) >= 2
    reconnect = next(c for c in STORAGE_PERSISTENCE_CASES if c["sort_order"] == 10)
    assert "re-authenticate" not in str(reconnect)
    sensor = next(c for c in STORAGE_PERSISTENCE_CASES if c["sort_order"] == 11)
    assert "guarantees zero" not in str(sensor)
    assert "acknowledged" in sensor["rubric"]["reference_answer"]


def test_seed_is_idempotent_and_every_enabled_concept_has_authored_cases(db):
    seed_authored_data(db)
    original = {row.id: row.version for row in db.query(CasePrompt)}
    seed_authored_data(db)
    assert {row.id: row.version for row in db.query(CasePrompt)} == original
    assert db.query(CasePrompt).filter_by(active=True).count() == sum(map(len, CASE_BANKS.values()))
    for concept in db.query(Concept).filter_by(enabled=True):
        assert db.query(CasePrompt).filter_by(concept_id=concept.id, active=True).count() >= 7


def test_seed_content_change_creates_version_without_rewriting_attempt_or_key(db):
    seed_authored_data(db)
    original = db.query(CasePrompt).filter_by(authored_id=STORAGE_PERSISTENCE_CASES[0]["authored_id"]).one()
    old_id, old_text, old_reference = original.id, original.scenario_text, original.rubric.reference_answer
    session = Session(owner_id="test-owner", concept_id=original.concept_id, current_prompt_id=old_id)
    db.add(session)
    db.flush()
    attempt = Attempt(session_id=session.id, case_prompt_id=old_id, rubric_version=original.rubric.version,
                      stage="diagnostic", answer_text="An original historical answer.")
    db.add(attempt)
    db.commit()
    changed = deepcopy(CASE_BANKS)
    changed["storage-persistence"][0]["scenario_text"] += " Added explicit condition."
    changed["storage-persistence"][0]["rubric"]["reference_answer"] += " Added expected reasoning."
    seed_authored_data(db, changed)
    db.expire_all()
    old = db.get(CasePrompt, old_id)
    new = db.query(CasePrompt).filter_by(authored_id=original.authored_id, active=True).one()
    assert old.scenario_text == old_text and old.rubric.reference_answer == old_reference
    assert old.active is False and new.id != old.id and new.version == old.version + 1
    assert db.get(Attempt, attempt.id).case_prompt_id == old_id
    assert db.get(Session, session.id).current_prompt_id == old_id
    seed_authored_data(db, changed)
    assert db.query(CasePrompt).filter_by(authored_id=original.authored_id).count() == 2


def test_seed_preserves_user_authored_rows_and_retires_identifiable_legacy_seed_only(db):
    concept = Concept(module="B", slug="storage-persistence", title="Storage", description="Existing", enabled=True)
    db.add(concept)
    db.flush()
    legacy_data = deepcopy(STORAGE_PERSISTENCE_CASES[0])
    legacy_data.pop("authored_id")
    rubric = legacy_data.pop("rubric")
    legacy = CasePrompt(concept_id=concept.id, **legacy_data)
    custom = CasePrompt(concept_id=concept.id, scenario_text="My own storage question", stage="apply",
                        source="human-authored", sort_order=1)
    custom_ai = CasePrompt(concept_id=concept.id, scenario_text="My independently authored AI question", stage="apply",
                           source="ai-authored", sort_order=1)
    db.add_all([legacy, custom, custom_ai])
    db.flush()
    db.add(Rubric(case_prompt_id=legacy.id, **rubric))
    db.commit()
    old_reference = legacy.rubric.reference_answer
    seed_authored_data(db)
    db.expire_all()
    assert db.get(CasePrompt, legacy.id).active is False
    assert db.get(CasePrompt, legacy.id).rubric.reference_answer == old_reference
    assert db.get(CasePrompt, custom.id).active is True
    assert db.get(CasePrompt, custom_ai.id).active is True


def test_authored_lessons_are_served_with_safe_html_and_honest_provenance():
    for concept in CONCEPTS:
        html = render_resource(concept["slug"])
        assert "AI-authored" in html and "unreviewed" in html
        assert "<pre>" in html and "Practice" in html
        assert "<script" not in html and "reference_answer" not in html
    with pytest.raises(KeyError):
        render_resource("../../.env")


def test_authored_resource_routes_return_html_and_reject_unknown_slugs():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.resources import RESOURCE_VERSION, router

    isolated_app = FastAPI()
    isolated_app.include_router(router)
    client = TestClient(isolated_app)
    for slug in CASE_BANKS:
        response = client.get(f"/v1/resources/{slug}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert response.headers["x-resource-version"] == RESOURCE_VERSION
        assert "default-src 'none'" in response.headers["content-security-policy"]
    assert client.get("/v1/resources/unknown").status_code == 404


def test_exact_reseed_preserves_existing_human_review_label(db):
    seed_authored_data(db)
    row = db.query(CasePrompt).filter_by(authored_id=STORAGE_PERSISTENCE_CASES[0]["authored_id"]).one()
    row.review_status = "reviewed"
    original_id = row.id
    db.commit()
    seed_authored_data(db)
    assert db.get(CasePrompt, original_id).review_status == "reviewed"
    assert db.query(CasePrompt).filter_by(authored_id=row.authored_id).count() == 1


@pytest.mark.parametrize("review_status", ["reviewed", "rejected"])
@pytest.mark.parametrize("corrected_content", [False, True])
@pytest.mark.parametrize("new_shipped_content", [False, True])
def test_reseed_preserves_reviewer_lineage_and_inactive_rejection_tombstone(
    db, review_status, corrected_content, new_shipped_content,
):
    """Use the actual review API clone, not an in-place review-status shortcut."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.db.database import get_db
    from app.routers.review import review_router, verify_reviewer_auth

    seed_authored_data(db)
    original = db.query(CasePrompt).filter_by(authored_id=STORAGE_PERSISTENCE_CASES[0]["authored_id"]).one()
    original_id, identity = original.id, original.authored_id
    original_text, original_key = original.scenario_text, original.rubric.reference_answer
    session = Session(owner_id="historical-owner", concept_id=original.concept_id, current_prompt_id=original_id)
    db.add(session)
    db.flush()
    attempt = Attempt(session_id=session.id, case_prompt_id=original_id, rubric_version=original.rubric.version,
                      stage="diagnostic", answer_text="An answer from before the content review.")
    db.add(attempt)
    db.commit()

    isolated_app = FastAPI()
    isolated_app.include_router(review_router)
    isolated_app.dependency_overrides[get_db] = lambda: db
    isolated_app.dependency_overrides[verify_reviewer_auth] = lambda: True
    body = {"review_status": review_status, "reviewer_name": "Content reviewer",
            "reviewer_notes": "Decision for this authored lineage."}
    if corrected_content:
        body.update(scenario_text="Human-corrected scenario with explicit assumptions.",
                    reference_answer="Human-corrected reference reasoning.",
                    assumptions=["The human-approved assumption"])
    with TestClient(isolated_app) as client:
        response = client.post(f"/v1/review/cases/{original_id}", json=body)
    assert response.status_code == 200, response.text
    reviewed_id = response.json()["case_id"]
    db.expire_all()
    decision = db.query(CaseReviewRevision).filter_by(source_case_id=original_id, reviewed_case_id=reviewed_id).one()
    assert decision.review_status == review_status
    expected_text = db.get(CasePrompt, reviewed_id).scenario_text
    expected_key = db.get(CasePrompt, reviewed_id).rubric.reference_answer
    seed_banks = deepcopy(CASE_BANKS)
    if new_shipped_content:
        seed_banks["storage-persistence"][0]["scenario_text"] += " A later shipped edit without a review decision."
        seed_banks["storage-persistence"][0]["rubric"]["reference_answer"] += " An unapproved shipped correction."

    for _ in range(2):
        seed_authored_data(db, seed_banks)
        db.expire_all()
        versions = db.query(CasePrompt).filter_by(authored_id=identity).all()
        assert len(versions) == 2, "startup must not introduce an unapproved competing version"
        old, reviewed = db.get(CasePrompt, original_id), db.get(CasePrompt, reviewed_id)
        assert old.active is False, "the original seed must not be resurrected after review"
        assert reviewed.active is (review_status == "reviewed")
        assert reviewed.review_status == review_status and reviewed.version == 2
        assert reviewed.scenario_text == expected_text and reviewed.rubric.reference_answer == expected_key
        assert old.scenario_text == original_text and old.rubric.reference_answer == original_key
        assert db.get(Session, session.id).current_prompt_id == original_id
        assert db.get(Attempt, attempt.id).case_prompt_id == original_id
        assert db.query(CaseReviewRevision).filter_by(source_case_id=original_id).count() == 1
        if review_status == "rejected":
            assert not any(version.active for version in versions), "rejection remains an inactive lineage tombstone"
