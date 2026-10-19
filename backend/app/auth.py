"""Authentication and user session management.

Supports:
1. Verified email/password authentication with JWT bearer tokens.
2. Server-issued session cookies (with seamless anonymous-to-user upgrade).
3. Derived owner_id for scoping sessions and attempt evidence.
"""

from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import uuid
from typing import Optional

from fastapi import Request, Response, Depends
from itsdangerous import URLSafeSerializer
import jwt
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.database import get_db
from app.db.models import User


# ── Password Hashing (PBKDF2-HMAC-SHA256) ─────────────────────────

def hash_password(password: str) -> str:
    """Hash password with a random 16-byte salt using PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100_000)
    return f"pbkdf2:sha256:100000${salt.hex()}${key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against stored PBKDF2 hash with constant-time comparison."""
    try:
        parts = hashed_password.split("$")
        if len(parts) != 3 or not parts[0].startswith("pbkdf2:sha256:"):
            return False
        iterations = int(parts[0].split(":")[2])
        salt = bytes.fromhex(parts[1])
        expected_key = bytes.fromhex(parts[2])
        actual_key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, iterations)
        return hmac.compare_digest(actual_key, expected_key)
    except Exception:
        return False


# ── JWT Token Utilities ──────────────────────────────────────────

def create_access_token(user_id: str, email: str, expires_delta: Optional[timedelta] = None) -> str:
    """Generate a signed HS256 JWT access token."""
    settings = get_settings()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(days=30))
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def decode_access_token(token: str) -> Optional[dict]:
    """Verify and decode a signed JWT access token."""
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except Exception:
        return None


# ── Session & Ownership Extraction ───────────────────────────────

def _get_serializer() -> URLSafeSerializer:
    settings = get_settings()
    return URLSafeSerializer(settings.secret_key, salt="concept-check-session")


def get_owner_id(request: Request, response: Response) -> str:
    """Derive owner ID from JWT Bearer token, session cookie, or anonymous ID."""
    # 1. Bearer Token in Authorization header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        payload = decode_access_token(token)
        if payload and payload.get("sub"):
            return payload["sub"]

    # 2. Signed Cookie
    serializer = _get_serializer()
    cookie_value = request.cookies.get("cc_session")

    owner_id = None
    if cookie_value:
        # Check if cookie itself is a JWT token
        payload = decode_access_token(cookie_value)
        if payload and payload.get("sub"):
            return payload["sub"]

        # Check serializer
        try:
            owner_id = serializer.loads(cookie_value)
        except Exception:
            owner_id = None

    if not owner_id:
        owner_id = str(uuid.uuid4())
        signed = serializer.dumps(owner_id)
        response.set_cookie(
            key="cc_session",
            value=signed,
            httponly=True,
            secure=get_settings().environment.lower() in {"production", "prod"},
            samesite="lax",
            max_age=60 * 60 * 24 * 30,  # 30 days
        )

    return owner_id


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Retrieve the currently authenticated User or None if unauthenticated."""
    auth_header = request.headers.get("Authorization")
    token = None
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
    elif request.cookies.get("cc_auth_token"):
        token = request.cookies.get("cc_auth_token")

    if not token:
        return None

    payload = decode_access_token(token)
    if not payload or not payload.get("sub"):
        return None

    user = db.get(User, payload["sub"])
    return user
