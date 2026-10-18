"""Data export and migration tool for Concept Check.

Enables moving records from SQLite to Supabase Postgres while preserving:
- All UUIDs and stable IDs
- Foreign key relationships and order
- Timestamps (created_at, updated_at, reviewed_at)
- Assessment versions and reviewer states

Usage:
  Export to JSON:
    python -m app.db.migrate_data export data_export.json

  Import into target database:
    python -m app.db.migrate_data import data_export.json --target-url postgresql://user:pass@host:5432/db
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base, SessionLocal
from app.db.models import (
    Concept, CasePrompt, Rubric, Session, Message,
    Attempt, Gap, CriterionAssessment, Intervention,
    Attachment, Transcription, TurnIdempotency,
)

# Ordered list of models to respect foreign key constraints
TABLE_ORDER = [
    Concept,
    CasePrompt,
    Rubric,
    Session,
    Transcription,
    Attachment,
    Attempt,
    Gap,
    CriterionAssessment,
    Intervention,
    TurnIdempotency,
    Message,
]


def _serialize_val(val: Any) -> Any:
    if isinstance(val, datetime):
        return val.isoformat()
    return val


def export_data(filepath: str):
    """Export all tables to a structured JSON file."""
    db = SessionLocal()
    export_payload: dict[str, list[dict]] = {}

    try:
        for model in TABLE_ORDER:
            table_name = model.__tablename__
            rows = db.query(model).all()
            table_records = []
            for row in rows:
                row_dict = {}
                for col in model.__table__.columns:
                    val = getattr(row, col.name)
                    row_dict[col.name] = _serialize_val(val)
                table_records.append(row_dict)
            export_payload[table_name] = table_records
            print(f"Exported {len(table_records)} rows from {table_name}")

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_payload, f, indent=2, ensure_ascii=False)
        print(f"Export complete -> {filepath}")

    finally:
        db.close()


def import_data(filepath: str, target_url: str):
    """Import records into target database (e.g. Supabase Postgres)."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    target_engine = create_engine(target_url)
    TargetSession = sessionmaker(bind=target_engine)

    # Ensure tables exist
    Base.metadata.create_all(bind=target_engine)

    session = TargetSession()
    try:
        for model in TABLE_ORDER:
            table_name = model.__tablename__
            records = data.get(table_name, [])
            for rec in records:
                # Convert ISO datetimes back to datetime objects
                for col in model.__table__.columns:
                    val = rec.get(col.name)
                    if val and col.type.python_type is datetime:
                        try:
                            rec[col.name] = datetime.fromisoformat(val)
                        except Exception:
                            pass
                obj = model(**rec)
                session.merge(obj)
            session.flush()
            print(f"Imported {len(records)} rows into {table_name}")

        session.commit()
        print("Import completed successfully!")
    except Exception as e:
        session.rollback()
        print(f"Import failed: {e}", file=sys.stderr)
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(description="Concept Check Data Migration")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Export command
    exp = subparsers.add_parser("export", help="Export SQLite data to JSON")
    exp.add_argument("file", help="Destination JSON path")

    # Import command
    imp = subparsers.add_parser("import", help="Import JSON data into target DB")
    imp.add_argument("file", help="Source JSON path")
    imp.add_argument("--target-url", required=True, help="Target SQLAlchemy DATABASE_URL")

    args = parser.parse_args()

    if args.command == "export":
        export_data(args.file)
    elif args.command == "import":
        import_data(args.file, args.target_url)


if __name__ == "__main__":
    main()
