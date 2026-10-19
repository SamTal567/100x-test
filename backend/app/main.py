"""Concept Check — FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.database import engine, Base, SessionLocal
from app.db.migrate_columns import ensure_schema_columns
from app.routers.concepts import router as concepts_router
from app.routers.sessions import router as sessions_router
from app.routers.review import attachments_router, review_router
from app.schemas import HealthResponse
from app.seed_data.seeding import seed_authored_data
from app.resources import router as resources_router
from app.routers.auth import router as auth_router


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables, ensure columns, and seed initial data on startup."""
    Base.metadata.create_all(bind=engine)
    ensure_schema_columns(engine)
    _seed_data()
    yield


app = FastAPI(
    title="Concept Check API",
    description="Backend concepts understanding assessment tool",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(concepts_router)
app.include_router(sessions_router)
app.include_router(attachments_router)
app.include_router(review_router)
app.include_router(resources_router)
app.include_router(auth_router)



@app.get("/health", response_model=HealthResponse)
def health():
    """Health check with provider availability status."""
    return HealthResponse(
        status="ok",
        openai_available=settings.openai_available,
        fish_audio_available=settings.fish_audio_available,
    )


def _seed_data():
    """Apply immutable authored versions, raising rather than hiding seed failures."""
    with SessionLocal() as db:
        seed_authored_data(db)
