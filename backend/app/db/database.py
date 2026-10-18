# ==============================================================================
# SQLAlchemy Database Engine and Session Management
# ==============================================================================
# This module sets up the database connection pipeline for the entire app.
# It does three main things:
#   1. Creates the Database Engine (the low-level connection manager).
#   2. Configures the Session Factory (which spawns database sessions).
#   3. Provides a request-scoped dependency (`get_db`) that ensures every API
#      request gets its own database session and closes it safely when done.
# ==============================================================================

# `create_engine`: Connects Python to the database and manages connection pooling.
from sqlalchemy import create_engine

# `sessionmaker`: A factory that creates individual database sessions (units of work).
# `DeclarativeBase`: The modern SQLAlchemy 2.0 base class used to define database models.
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Import our application settings (contains DATABASE_URL, etc.)
from app.config import get_settings


# Load cached settings (defined in config.py)
settings = get_settings()

# ------------------------------------------------------------------------------
# 1. SQLite Concurrency Configuration
# ------------------------------------------------------------------------------
# By default, Python's SQLite driver only allows the thread that created a 
# connection to use it. However, FastAPI handles incoming web requests across a
# threadpool. Setting `check_same_thread = False` tells SQLite it is safe to 
# allow multiple threads to interact with the connection.
# (If using PostgreSQL, connect_args remains empty because Postgres handles this natively).
connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

# ------------------------------------------------------------------------------
# 2. Database Engine Creation
# ------------------------------------------------------------------------------
# The engine is the central object that knows how to speak the dialect of our
# database (SQLite, Postgres, etc.) and maintains the underlying connection pool.
engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    echo=False,  # Set to True if you want to print all generated raw SQL queries to console
)

# ------------------------------------------------------------------------------
# 3. Session Factory (SessionLocal)
# ------------------------------------------------------------------------------
# `SessionLocal` is a class factory (not a session itself). Calling `SessionLocal()`
# will instantiate a new database session.
# - `autocommit=False`: Transactions will not commit automatically. We must explicitly
#   call `db.commit()` to save changes, giving us atomic control over checkpoints.
# - `autoflush=False`: Changes won't be pushed prematurely to the DB until we say so.
# - `bind=engine`: Links these sessions to our database engine configured above.
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ------------------------------------------------------------------------------
# 4. Declarative Base Model
# ------------------------------------------------------------------------------
# In SQLAlchemy 2.0, all our ORM models (tables like Concept, Session, Attempt)
# will inherit from this `Base` class. It maintains a registry of all mapped tables.
class Base(DeclarativeBase):
    pass


# ------------------------------------------------------------------------------
# 5. Database Session Dependency (FastAPI get_db)
# ------------------------------------------------------------------------------
# This function is used with FastAPI's dependency injection: `db = Depends(get_db)`.
# It uses Python's `yield` generator and a `try...finally` block:
#   1. `db = SessionLocal()` opens a fresh database session for an incoming request.
#   2. `yield db` hands that session over to the endpoint to run queries.
#   3. `finally: db.close()` is guaranteed to execute when the request finishes
#      (even if an error or crash occurs), preventing database connection leaks.
def get_db():
    """Dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

