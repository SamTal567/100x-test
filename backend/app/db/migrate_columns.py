"""Non-destructive SQLite/PostgreSQL schema upgrade helper.

Safely checks and adds any missing columns on startup without dropping tables
or disturbing existing records.
"""

import logging
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Table -> list of (column_name, column_type_ddl)
COLUMNS_TO_ENSURE = {
    "case_prompts": [
        ("authored_id", "VARCHAR(100)"),
        ("active", "BOOLEAN NOT NULL DEFAULT true"),
        ("response_format", "VARCHAR(30) DEFAULT 'written'"),
        ("assumptions", "JSON"),
        ("diagram_preset", "JSON"),
        ("cloze_preset", "JSON"),
        ("question_parts", "JSON"),
    ],
    "attempts": [
        ("diagram_state", "JSON"),
        ("cloze_state", "JSON"),
        ("skill_id", "VARCHAR(50)"),
        ("case_snapshot", "JSON"),
        ("question_parts_coverage", "JSON"),
        ("support_level", "VARCHAR(50) NOT NULL DEFAULT 'unknown'"),
        ("processing_status", "VARCHAR(20) NOT NULL DEFAULT 'complete'"),
    ],
    "sessions": [
        ("baseline_analysis_status", "VARCHAR(20) NOT NULL DEFAULT 'unknown'"),
        ("baseline_prompt_ids", "JSON"),
        ("processing_turn_id", "VARCHAR(100)"),
        ("processing_status", "VARCHAR(20) NOT NULL DEFAULT 'idle'"),
    ],
    "messages": [
        ("provider_status", "VARCHAR(30) NOT NULL DEFAULT 'complete'"),
    ],
    "interventions": [
        ("gap_id", "VARCHAR(36) REFERENCES gaps(id)"),
        ("status", "VARCHAR(30) NOT NULL DEFAULT 'delivered'"),
    ],
    "criterion_assessments": [
        ("skill_id", "VARCHAR(50)"),
        ("rating", "VARCHAR(40) DEFAULT 'ambiguous_needs_clarification'"),
        ("question_part_id", "VARCHAR(100)"),
        ("coverage", "VARCHAR(30)"),
        ("issue_type", "VARCHAR(40)"),
        ("demonstrated_explanation", "TEXT"),
        ("explanation", "TEXT"),
        ("next_action", "TEXT"),
    ],
    "turn_idempotency": [
        ("request_body_hash", "VARCHAR(64)"),
        ("request_payload", "JSON"),
        ("state", "VARCHAR(20) NOT NULL DEFAULT 'complete'"),
        ("attempt_id", "VARCHAR(36)"),
    ],
    "users": [
        ("email", "VARCHAR(255)"),
        ("hashed_password", "VARCHAR(255)"),
        ("full_name", "VARCHAR(255)"),
        ("created_at", "TIMESTAMP"),
        ("updated_at", "TIMESTAMP"),
    ],
}



def protect_owned_user_table(conn) -> None:
    """Protect the account table as its existing PostgreSQL owner only.

    Supabase's management connection does not own this runtime-created table.
    The backend owner keeps normal owner access; no public Data API role gets
    a policy. SQLite and deployments owned by another role are left untouched.
    """
    if conn.dialect.name != "postgresql":
        return
    owns_table = conn.execute(text("""
        SELECT tableowner = current_user FROM pg_tables
        WHERE schemaname = 'public' AND tablename = 'users'
    """)).scalar()
    if owns_table:
        conn.execute(text("REVOKE ALL ON TABLE public.users FROM PUBLIC, anon, authenticated"))
        conn.execute(text("ALTER TABLE public.users ENABLE ROW LEVEL SECURITY"))


def ensure_schema_columns(engine: Engine) -> None:
    """Check each table and add any newly introduced columns if missing."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table_name, columns in COLUMNS_TO_ENSURE.items():
            if table_name not in existing_tables:
                continue
            existing_cols = {col["name"] for col in inspector.get_columns(table_name)}
            for col_name, col_type in columns:
                if col_name not in existing_cols:
                    logger.info("Adding column %s to %s", col_name, table_name)
                    try:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}"))
                        if table_name == "criterion_assessments" and col_name == "rating":
                            # Only initialize a NEW detail column. Existing detailed judgments
                            # are historical evidence and must never be rewritten at startup.
                            conn.execute(text("""
                                UPDATE criterion_assessments SET rating = CASE
                                    WHEN met = true THEN 'demonstrated'
                                    WHEN met = false THEN 'not_addressed'
                                    ELSE 'ambiguous_needs_clarification'
                                END
                            """))
                    except Exception as exc:
                        logger.warning("Could not add column %s to %s (permission or concurrent): %s", col_name, table_name, exc)

        protect_owned_user_table(conn)
