"""Preserve authored versions, review history and recoverable processing.

Revision ID: a14f20261018
Revises: e8a1d47b718c
"""

from alembic import op
import sqlalchemy as sa

revision = "a14f20261018"
down_revision = "e8a1d47b718c"
branch_labels = None
depends_on = None


# Includes fields introduced by the former startup-only upgrades, so upgrading
# from the initial Alembic revision produces the complete current contract.
COLUMNS = {
    "case_prompts": [
        ("authored_id", "VARCHAR(100)"), ("active", "BOOLEAN NOT NULL DEFAULT true"),
        ("response_format", "VARCHAR(30) DEFAULT 'written'"),
        ("assumptions", "JSON"), ("diagram_preset", "JSON"), ("cloze_preset", "JSON"),
    ],
    "sessions": [
        ("baseline_analysis_status", "VARCHAR(20) NOT NULL DEFAULT 'unknown'"),
        ("baseline_prompt_ids", "JSON"), ("processing_turn_id", "VARCHAR(100)"),
        ("processing_status", "VARCHAR(20) NOT NULL DEFAULT 'idle'"),
    ],
    "attempts": [
        ("diagram_state", "JSON"), ("cloze_state", "JSON"), ("skill_id", "VARCHAR(50)"),
        ("case_snapshot", "JSON"), ("support_level", "VARCHAR(50) NOT NULL DEFAULT 'unknown'"),
        ("processing_status", "VARCHAR(20) NOT NULL DEFAULT 'complete'"),
    ],
    "messages": [("provider_status", "VARCHAR(30) NOT NULL DEFAULT 'complete'")],
    "interventions": [
        ("gap_id", "VARCHAR(36) REFERENCES gaps(id)"),
        ("status", "VARCHAR(30) NOT NULL DEFAULT 'delivered'"),
    ],
    "criterion_assessments": [
        ("skill_id", "VARCHAR(50)"),
        ("rating", "VARCHAR(40) DEFAULT 'ambiguous_needs_clarification'"),
    ],
    "turn_idempotency": [
        ("request_body_hash", "VARCHAR(64)"), ("request_payload", "JSON"),
        ("state", "VARCHAR(20) NOT NULL DEFAULT 'complete'"), ("attempt_id", "VARCHAR(36)"),
    ],
}


def upgrade():
    connection = op.get_bind()
    inspector = sa.inspect(connection)
    for table, columns in COLUMNS.items():
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, ddl in columns:
            if name in existing:
                continue
            op.execute(sa.text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            if table == "criterion_assessments" and name == "rating":
                op.execute(sa.text("""
                    UPDATE criterion_assessments SET rating = CASE
                        WHEN met = true THEN 'demonstrated'
                        WHEN met = false THEN 'not_addressed'
                        ELSE 'ambiguous_needs_clarification'
                    END
                """))

    tables = set(inspector.get_table_names())
    if "assessment_review_revisions" not in tables:
        op.create_table(
            "assessment_review_revisions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("assessment_id", sa.String(36), sa.ForeignKey("criterion_assessments.id"), nullable=False),
            sa.Column("reviewer_name", sa.String(100), nullable=False),
            sa.Column("proposal_snapshot", sa.JSON(), nullable=False),
            sa.Column("previous_snapshot", sa.JSON(), nullable=False),
            sa.Column("review_snapshot", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_assessment_review_revisions_assessment_id", "assessment_review_revisions", ["assessment_id"])
    if "case_review_revisions" not in tables:
        op.create_table(
            "case_review_revisions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("source_case_id", sa.String(36), sa.ForeignKey("case_prompts.id"), nullable=False),
            sa.Column("reviewed_case_id", sa.String(36), sa.ForeignKey("case_prompts.id"), nullable=False),
            sa.Column("reviewer_name", sa.String(100), nullable=False),
            sa.Column("review_status", sa.String(20), nullable=False),
            sa.Column("reviewer_notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_case_review_revisions_source_case_id", "case_review_revisions", ["source_case_id"])
    indexes = {index["name"] for index in sa.inspect(connection).get_indexes("case_prompts")}
    if "ix_case_prompts_authored_id" not in indexes:
        op.create_index("ix_case_prompts_authored_id", "case_prompts", ["authored_id"], unique=False)


def downgrade():
    raise RuntimeError("This migration retains learner evidence and review history; restore a verified backup to roll back.")
