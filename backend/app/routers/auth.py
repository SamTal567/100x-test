"""User authentication router (Sign Up, Sign In, Sign Out, Me).

Provides JWT-based authentication with password hashing and session migration.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from itsdangerous import BadData
from sqlalchemy import func, update
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    decode_access_token,
    get_current_user,
    hash_password,
    verify_password,
    _get_serializer,
)
from app.config import get_settings
from app.db.database import get_db
from app.db.models import Attachment, Session as LearningSession, Transcription, User
from app.schemas import AuthResponse, AuthStatus, UserLoginRequest, UserOut, UserRegisterRequest

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _claim_anonymous_sessions(db: Session, request: Request, user_id: str):
    """Move sessions and their owned media in the caller's auth transaction."""
    cookie_value = request.cookies.get("cc_session")
    if not cookie_value:
        return

    # Don't claim if cookie was already another valid user token
    existing_jwt = decode_access_token(cookie_value)
    if existing_jwt and existing_jwt.get("sub"):
        return

    serializer = _get_serializer()
    try:
        anon_owner_id = serializer.loads(cookie_value)
    except BadData:
        return
    if not isinstance(anon_owner_id, str) or not anon_owner_id or anon_owner_id == user_id:
        return

    session_ids = [row.id for row in db.query(LearningSession.id).filter_by(owner_id=anon_owner_id)]
    if not session_ids:
        return
    for model in (Attachment, Transcription):
        db.execute(
            update(model)
            .where(model.session_id.in_(session_ids), model.owner_id == anon_owner_id)
            .values(owner_id=user_id)
        )
    db.execute(
        update(LearningSession)
        .where(LearningSession.id.in_(session_ids), LearningSession.owner_id == anon_owner_id)
        .values(owner_id=user_id)
    )


def _auth_cookie_options():
    return {
        "path": "/",
        "httponly": True,
        "secure": get_settings().environment.strip().lower() in {"production", "prod"},
        "samesite": "lax",
    }


def _set_auth_cookie(response: Response, token: str):
    # Keep cc_session JWT compatibility for existing browsers.
    for key in ("cc_auth_token", "cc_session"):
        response.set_cookie(key=key, value=token, max_age=60 * 60 * 24 * 30, **_auth_cookie_options())


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(
    req: UserRegisterRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Create a new user account and return JWT access token."""
    normalized_email = req.email.strip().lower()
    existing = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists. Please sign in instead.",
        )

    user = User(
        email=normalized_email,
        hashed_password=hash_password(req.password),
        full_name=req.full_name.strip() if req.full_name else None,
    )
    db.add(user)
    try:
        db.flush()
        _claim_anonymous_sessions(db, request, user.id)
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(user)

    token = create_access_token(user.id, user.email)
    _set_auth_cookie(response, token)

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.post("/login", response_model=AuthResponse)
def login(
    req: UserLoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Authenticate with email and password and return JWT access token."""
    normalized_email = req.email.strip().lower()
    user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
    if not user or not verify_password(req.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password. Please check your credentials.",
        )

    # Claim any anonymous sessions created before logging in
    try:
        _claim_anonymous_sessions(db, request, user.id)
        db.commit()
    except Exception:
        db.rollback()
        raise

    token = create_access_token(user.id, user.email)
    _set_auth_cookie(response, token)

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserOut.model_validate(user),
    )


@router.post("/logout")
def logout(response: Response):
    """Clear authentication cookies."""
    for key in ("cc_auth_token", "cc_session"):
        response.delete_cookie(key=key, **_auth_cookie_options())
    return {"status": "logged_out"}


@router.get("/me", response_model=AuthStatus)
def me(current_user: User = Depends(get_current_user)):
    """Return the profile of the authenticated user or status unauthenticated."""
    if not current_user:
        return AuthStatus(authenticated=False, user=None)
    return AuthStatus(
        authenticated=True,
        user=UserOut.model_validate(current_user),
    )
