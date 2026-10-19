"""User authentication router (Sign Up, Sign In, Sign Out, Me).

Provides JWT-based authentication with password hashing and session migration.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
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
from app.db.models import Session as LearningSession, User
from app.schemas import AuthResponse, AuthStatus, UserLoginRequest, UserOut, UserRegisterRequest

router = APIRouter(prefix="/v1/auth", tags=["auth"])


def _claim_anonymous_sessions(db: Session, request: Request, user_id: str):
    """Transfer any anonymous sessions created in the current browser session to the authenticated user."""
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
        if anon_owner_id and anon_owner_id != user_id:
            db.execute(
                update(LearningSession)
                .where(LearningSession.owner_id == anon_owner_id)
                .values(owner_id=user_id)
            )
            db.commit()
    except Exception:
        pass


def _set_auth_cookie(response: Response, token: str):
    settings = get_settings()
    is_prod = settings.environment.lower() in {"production", "prod"}
    response.set_cookie(
        key="cc_auth_token",
        value=token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,  # 30 days
    )
    # Also update cc_session to the user JWT so existing get_owner_id seamlessly sees it
    response.set_cookie(
        key="cc_session",
        value=token,
        httponly=True,
        secure=is_prod,
        samesite="lax",
        max_age=60 * 60 * 24 * 30,
    )


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
    db.commit()
    db.refresh(user)

    # Claim any anonymous sessions created prior to registering
    _claim_anonymous_sessions(db, request, user.id)

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
    _claim_anonymous_sessions(db, request, user.id)

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
    response.delete_cookie(key="cc_auth_token")
    response.delete_cookie(key="cc_session")
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
