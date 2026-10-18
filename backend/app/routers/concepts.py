"""Concepts API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DBSession

from app.db.database import get_db
from app.db.models import Concept
from app.schemas import ConceptOut

router = APIRouter(prefix="/v1/concepts", tags=["concepts"])


@router.get("", response_model=list[ConceptOut])
def list_concepts(db: DBSession = Depends(get_db)):
    """List all concepts in the catalogue."""
    concepts = (
        db.query(Concept)
        .order_by(Concept.sort_order)
        .all()
    )
    return [ConceptOut.model_validate(c) for c in concepts]
